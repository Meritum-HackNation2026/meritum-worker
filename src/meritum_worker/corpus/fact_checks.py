"""Fact-checkers' ratings for a check's facts, from Google Fact Check Tools API.

Each fact is one plain query, masked before it leaves. A review counts only when
its publisher is in the catalogue (Demagog included: its ``publisher_id`` only
names the publisher, its pages are never fetched). Whether the rated claim is our
claim is judged later, by the model, in the evidence step.

Features:
    US-KOR-01, US-BEZ-03, F-14, F-18, ADR-24, ADR-34
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.web_search import catalog_entry_for
from meritum_core.evidence.models import FoundClaimReview
from meritum_core.security.pii import PiiGatePort, mask_personal_data
from pydantic import BaseModel, ConfigDict, ValidationError

from meritum_worker.corpus.constants import MAX_PARALLEL_CLAIMS, WEB_QUERIES_PER_CHECK
from meritum_worker.corpus.fact_check_constants import (
    FACT_CHECK_LANGUAGE,
    REVIEW_TITLE_MAX_CHARS,
)
from meritum_worker.corpus.fact_check_ports import FactCheckPort
from meritum_worker.corpus.models import FactCheckHit


class ClaimReviewFinding(BaseModel):
    """One rating found for one fact, before the model compared the claims.

    Attributes:
        fact: The index of the fact among the check's facts.
        claim_reviewed: The claim the fact-checker rated (untrusted).
        found: The rating with the catalogue's facts about its publisher.
        cache_control: The API response's ``Cache-Control``, for the retention.

    Features:
        US-KOR-01, F-14, ADR-24, ADR-34
    """

    model_config = ConfigDict(frozen=True)

    fact: int
    claim_reviewed: str
    found: FoundClaimReview
    cache_control: str | None


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


async def search_fact_checks(
    facts: Sequence[str],
    port: FactCheckPort,
    pii: PiiGatePort,
    catalog: Sequence[CatalogEntry],
) -> FactCheckSearch:
    """Mask and search each fact, then keep the ratings of catalogue publishers.

    Args:
        facts: The checked facts, as extracted from the masked input.
        port: The Fact Check Tools API.
        pii: The masking gate every query goes through before it leaves.
        catalog: The loaded catalogue, excluded entries included.

    Returns:
        The findings, and the links of those on fetchable catalogue domains.

    An unavailable API propagates; the workflow maps it to the
    ``fact_check_unavailable`` limitation.

    Features:
        US-KOR-01, US-BEZ-03, F-14, F-18, ADR-24, ADR-34
    """
    asked = facts[:WEB_QUERIES_PER_CHECK]
    slots = asyncio.Semaphore(MAX_PARALLEL_CLAIMS)

    async def ask(query: str) -> tuple[list[FactCheckHit], str | None]:
        async with slots:
            masked = await mask_personal_data(query, pii)
            answer = await port.search(masked.text, language=FACT_CHECK_LANGUAGE)
            return answer.hits, answer.cache_control

    answers = await asyncio.gather(*map(ask, asked))
    fetched_at = datetime.now(UTC)
    findings = [
        finding
        for index, (hits, cache) in enumerate(answers)
        for hit in hits
        if (finding := _finding(index, hit, cache, catalog, fetched_at)) is not None
    ]
    links = dict.fromkeys(
        str(f.found.url)
        for f in findings
        if catalog_entry_for(str(f.found.url), catalog) is not None
    )
    return FactCheckSearch(
        calls=len(asked), findings=findings, article_urls=list(links)
    )


def _finding(
    fact: int,
    hit: FactCheckHit,
    cache_control: str | None,
    catalog: Sequence[CatalogEntry],
    fetched_at: datetime,
) -> ClaimReviewFinding | None:
    entry = _publisher(hit, catalog)
    if entry is None or hit.reviewed_at is None:
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
