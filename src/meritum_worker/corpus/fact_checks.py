"""Fact-checkers' ratings for a check's facts, from Google Fact Check Tools API.

Each fact is searched whole and by its key phrases, masked before it leaves; the
rated claims are compared with the fact by embeddings (worker#84). A review counts
only when its publisher is in the catalogue (Demagog included: its ``publisher_id`` only
names the publisher, its pages are never fetched). Whether the rated claim is our
claim is judged later, by the model, in the evidence step.

Features:
    US-KOR-01, US-ZRD-03, US-BEZ-03, F-14, F-15, F-18, ADR-24, ADR-34
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.web_search import catalog_entry_for
from meritum_core.evidence.models import FoundClaimReview
from meritum_core.security.pii import PiiGatePort, mask_personal_data
from meritum_core.shared.embeddings import (
    EmbeddingsPort,
    EmbeddingsUnavailableError,
)
from pydantic import BaseModel, ConfigDict, ValidationError

from meritum_worker.corpus.errors import FactCheckUnavailableError
from meritum_worker.corpus.fact_check_constants import (
    FACT_CHECK_CONTEXT_MIN_SIMILARITY,
    FACT_CHECK_LANGUAGE,
    FACT_CHECK_PARALLEL_QUERIES,
    FACT_CHECK_SIMILARITY_THRESHOLD,
    REVIEW_RATING_MAX_CHARS,
    REVIEW_TITLE_MAX_CHARS,
)
from meritum_worker.corpus.fact_check_ports import FactCheckPort
from meritum_worker.corpus.fact_check_queries import cosine, plan_queries
from meritum_worker.corpus.models import FactCheckAnswer, FactCheckHit


class ClaimReviewFinding(BaseModel):
    """One rating found for one fact, before the model compared the claims.

    Attributes:
        fact: The index of the fact among the check's facts.
        claim_reviewed: The claim the fact-checker rated (untrusted).
        found: The rating with the catalogue's facts about its publisher.
        cache_control: The API response's ``Cache-Control``, for the retention.
        similar: Whether ``claim_reviewed`` is close enough to the fact for the
            model's comparison; False keeps the rating as context only.

    Features:
        US-KOR-01, US-ZRD-03, F-14, F-15, ADR-24, ADR-34
    """

    model_config = ConfigDict(frozen=True)

    fact: int
    claim_reviewed: str
    found: FoundClaimReview
    cache_control: str | None
    similar: bool = True


class FactCheckSearch(BaseModel):
    """What the fact-check search found for one check.

    Attributes:
        calls: How many API searches were sent.
        findings: The ratings of publishers the catalogue knows.
        article_urls: Fact-check links on catalogue domains that may be fetched.

    Features:
        US-KOR-01, F-14, ADR-34
    """

    model_config = ConfigDict(frozen=True)

    calls: int
    findings: list[ClaimReviewFinding]
    article_urls: list[str]


async def search_fact_checks(  # ruff: ignore[too-many-arguments]  # the two optional ones are keyword-only
    facts: Sequence[str],
    port: FactCheckPort,
    pii: PiiGatePort,
    catalog: Sequence[CatalogEntry],
    *,
    phrases: Sequence[Sequence[str]] = (),
    embeddings: EmbeddingsPort | None = None,
) -> FactCheckSearch:
    """Search each fact and its key phrases, then keep the close ratings.

    The API matches phrases literally, so besides the full claim each fact's key
    phrases (names, places, numbers) are searched too, in parallel and masked
    first. The reviews are merged by link per fact. With ``embeddings`` each
    ``claimReviewed`` is compared with the fact: from
    FACT_CHECK_SIMILARITY_THRESHOLD it goes on to the model's comparison, from
    FACT_CHECK_CONTEXT_MIN_SIMILARITY it stays context, below it is dropped.
    The vectors are not kept anywhere. Without embeddings (or when they fail)
    every review goes on to the comparison.

    Args:
        facts: The checked facts, as extracted from the masked input.
        port: The Fact Check Tools API.
        pii: The masking gate every query goes through before it leaves.
        catalog: The loaded catalogue, excluded entries included.
        phrases: Each fact's key phrases, in the order of ``facts``.
        embeddings: The embeddings the reviewed claims are compared with.

    Returns:
        The findings, and the links of those on fetchable catalogue domains.

    Raises:
        FactCheckUnavailableError: Every query failed; the workflow maps it to
            the ``fact_check_unavailable`` limitation. A part failing is no error.

    Features:
        US-KOR-01, US-ZRD-03, US-BEZ-03, F-14, F-15, F-18, ADR-24, ADR-34
    """
    asked = plan_queries(facts, phrases)
    slots = asyncio.Semaphore(FACT_CHECK_PARALLEL_QUERIES)

    async def ask(query: str) -> FactCheckAnswer | FactCheckUnavailableError:
        async with slots:
            masked = await mask_personal_data(query, pii)
            try:
                return await port.search(masked.text, language=FACT_CHECK_LANGUAGE)
            except FactCheckUnavailableError as error:
                return error

    answers = await asyncio.gather(*(ask(query) for _, query in asked))
    failed = [a for a in answers if isinstance(a, FactCheckUnavailableError)]
    if failed and len(failed) == len(answers):
        raise FactCheckUnavailableError(str(failed[0])) from failed[0]
    fetched_at = datetime.now(UTC)
    merged: dict[tuple[int, str], ClaimReviewFinding] = {}
    for (fact, _), answer in zip(asked, answers, strict=True):
        if isinstance(answer, FactCheckUnavailableError):
            continue
        for hit in answer.hits:
            finding = _finding(fact, hit, answer.cache_control, catalog, fetched_at)
            if finding is not None:
                merged.setdefault((fact, str(finding.found.url)), finding)
    findings = await _by_similarity(facts, list(merged.values()), embeddings)
    links = dict.fromkeys(
        str(f.found.url)
        for f in findings
        if catalog_entry_for(str(f.found.url), catalog) is not None
    )
    return FactCheckSearch(
        calls=len(asked), findings=findings, article_urls=list(links)
    )


async def _by_similarity(
    facts: Sequence[str],
    findings: list[ClaimReviewFinding],
    embeddings: EmbeddingsPort | None,
) -> list[ClaimReviewFinding]:
    if embeddings is None or not findings:
        return findings
    try:
        vectors = await embeddings.embed_documents(
            [*facts, *(f.claim_reviewed for f in findings)]
        )
    except EmbeddingsUnavailableError:
        return findings
    kept: list[ClaimReviewFinding] = []
    for finding, vector in zip(findings, vectors[len(facts) :], strict=True):
        score = cosine(vectors[finding.fact], vector)
        if score >= FACT_CHECK_SIMILARITY_THRESHOLD:
            kept.append(finding)
        elif score >= FACT_CHECK_CONTEXT_MIN_SIMILARITY:
            kept.append(finding.model_copy(update={"similar": False}))
    return kept


def _finding(
    fact: int,
    hit: FactCheckHit,
    cache_control: str | None,
    catalog: Sequence[CatalogEntry],
    fetched_at: datetime,
) -> ClaimReviewFinding | None:
    entry = _publisher(hit, catalog)
    # A rating ClaimReviewPremise/Context cannot hold would fail the check later.
    too_long = len(hit.rating) > REVIEW_RATING_MAX_CHARS
    if entry is None or hit.reviewed_at is None or too_long:
        return None
    try:
        found = FoundClaimReview(
            publisher=entry.publisher,
            publisher_id=entry.publisher_id,
            signatory_of=list(entry.signatory_of),
            rating=hit.rating,
            title=hit.title[:REVIEW_TITLE_MAX_CHARS],
            reviewed_at=hit.reviewed_at,
            url=hit.url,
            fetched_at=fetched_at,
        )
    except ValidationError:
        return None  # a rating the contract cannot hold is no evidence
    return ClaimReviewFinding(
        fact=fact,
        claim_reviewed=hit.claim_reviewed,
        found=found,
        cache_control=cache_control,
    )


def _publisher(
    hit: FactCheckHit, catalog: Sequence[CatalogEntry]
) -> CatalogEntry | None:
    hosts = {_host(str(hit.url)), _host(hit.site)}
    return next(
        (
            e
            for e in catalog
            if e.kind == "fact_check" and _host(e.domain) in _suffixes(hosts)
        ),
        None,
    )


def _suffixes(hosts: set[str]) -> set[str]:
    # The publisher's own host and every parent domain below the public suffix.
    parts = [h.split(".") for h in hosts if h]
    return {".".join(p[i:]) for p in parts for i in range(len(p) - 1)}


def _host(value: str) -> str:
    raw = value if "//" in value else f"//{value}"
    return (urlsplit(raw).hostname or "").removeprefix("www.")
