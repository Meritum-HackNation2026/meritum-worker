"""Verdict, strength and validity from citations, by the core#41 rules (ADR-05).

Features:
    US-ZRD-04, US-ZRD-05, US-ZRD-10, US-SPR-04, US-SPR-05, F-15, ADR-25
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time

from meritum_core.checks.constants import DEFAULT_MAX_AGE_HOURS
from meritum_core.checks.contracts import (
    AGREEING_STANCE,
    CatalogEntry,
    Citation,
    ClaimDateSource,
    Stance,
    Verdict,
    is_stale,
)
from meritum_core.evidence import (
    EvidenceFacts,
    assign_validity,
    compute_strength,
    outdated_verdict,
    resolve_claim_date,
    settle_verdict,
)

from meritum_worker.evidence.models import Judgement


def resolve_check_claim_date(
    text_date: date | None,
    input_published_at: date | None,
    *,
    today: date,
) -> tuple[date, ClaimDateSource]:
    """Pick the claim date for evidence rules with ``resolve_claim_date``.

    Args:
        text_date: a date stated in the claim's text.
        input_published_at: the linked page's publication date, if any.
        today: the day the check ran.

    Returns:
        The claim date and its source label.

    Features:
        US-ZRD-05, F-15, ADR-25
    """
    published = (
        datetime.combine(input_published_at, time.min, tzinfo=UTC)
        if input_published_at is not None
        else None
    )
    claim_date, source = resolve_claim_date(text_date, published, today=today)
    return claim_date, source


def with_validity(
    citations: Sequence[Citation],
    catalog: Mapping[str, CatalogEntry],
    *,
    claim_date: date,
) -> list[Citation]:
    """Set each citation's validity at the claim date with ``assign_validity``.

    Args:
        citations: one fact's verified citations.
        catalog: catalogue entries by domain.
        claim_date: the date the claim refers to.

    Returns:
        The citations with validity set.

    Features:
        US-ZRD-05, US-ZRD-10, F-15, ADR-25
    """
    facts = [
        _facts(citation, catalog.get(citation.source.domain)) for citation in citations
    ]
    return assign_validity(facts, claim_date=claim_date)


def judge(
    citations: Sequence[Citation],
    *,
    catalog: Mapping[str, CatalogEntry],
    claim_date: date,
    present_tense: bool = False,
) -> Judgement:
    """Derive one fact's verdict, strength and technique from its citations.

    Args:
        citations: the verified citations with their validity.
        catalog: catalogue entries by domain.
        claim_date: the date the claim refers to.
        present_tense: whether the claim speaks about the present.

    Returns:
        The judgement; conflicting evidence has no strength.

    Features:
        US-ZRD-04, US-ZRD-10, US-SPR-04, US-SPR-05, F-15, ADR-05
    """
    stances = {c.stance for c in citations if c.validity != "superseded"}
    conflicting = {"supports", "refutes"} <= stances
    verdict = settle_verdict(_proposed(stances), citations)
    max_age = _max_age_hours(verdict, citations, catalog)
    technique = None
    archival = False
    if verdict != "insufficient_evidence":
        verdict, technique, archival = outdated_verdict(
            verdict,
            citations,
            claim_date=claim_date,
            present_tense=present_tense,
            max_age_hours=max_age,
        )
    strength = compute_strength(
        verdict,
        citations,
        claim_date=claim_date,
        max_age_hours=max_age,
    )
    shown = list(citations) if strength or conflicting else []
    return Judgement(
        verdict=verdict,
        strength=strength,
        citations=shown,
        technique=technique,
        archival=archival or (strength is not None and is_stale(strength.premises)),
    )


def _proposed(stances: set[Stance]) -> Verdict:
    if "supports" in stances:
        return "confirmed"
    if "refutes" in stances:
        return "false"
    return "insufficient_evidence"


def _facts(citation: Citation, entry: CatalogEntry | None) -> EvidenceFacts:
    return EvidenceFacts(
        citation=citation,
        entry_validity=entry.validity if entry else None,
        series=citation.source.domain,
    )


def _max_age_hours(
    verdict: Verdict,
    citations: Sequence[Citation],
    catalog: Mapping[str, CatalogEntry],
) -> int:
    stance = AGREEING_STANCE.get(verdict)
    agreeing = [
        c for c in citations if c.validity != "superseded" and c.stance == stance
    ]
    if not agreeing:
        return DEFAULT_MAX_AGE_HOURS
    dated = [c for c in agreeing if c.source.published_at is not None]
    if not dated:
        return DEFAULT_MAX_AGE_HOURS
    newest = max(dated, key=lambda c: c.source.published_at)
    entry = catalog.get(newest.source.domain)
    if entry is not None and entry.max_age_hours is not None:
        return entry.max_age_hours
    return DEFAULT_MAX_AGE_HOURS
