"""Assess each source's stance on each fact, one model call per pair.

Features:
    US-ZRD-01, US-ZRD-04, US-ZRD-10, F-15, F-16
"""

import asyncio
from datetime import date

from meritum_core.checks.contracts import Validity
from meritum_core.evidence import CitationDraft, SourceDocument
from meritum_core.shared.llm import LlmUsage

from meritum_worker import evidence
from meritum_worker.checks.models import CheckDeps, CheckState, ExtractedClaim
from meritum_worker.checks.usage import model_usage


async def assess_evidence(state: CheckState, deps: CheckDeps) -> CheckState:
    """Ask the model for the stance of every source on every fact, separately.

    Each fact's date is fixed first with ``resolve_claim_date`` (core#41).
    Each call sees one fact, its date and one source with the database's
    metadata; never the question or another source.

    Args:
        state: the check so far; a state that already has a result passes on.
        deps: the ports; the model is called and the catalogue read.

    Returns:
        The state with the dated claims, the proposed citations and the calls'
        usage.

    A model failure propagates; the workflow maps it to technical_failure.

    Features:
        US-ZRD-01, US-ZRD-04, US-ZRD-10, F-15, F-16
    """
    if state.result is not None:
        return state
    today = state.job.received_at.date()
    claims = [_claim_date(claim, state, today) for claim in state.claims]
    facts = [claim for claim in claims if claim.is_fact]
    validity = {entry.domain: entry.validity for entry in deps.catalog}
    # extract_claims dated every fact; an undated one has no age to judge by.
    pairs = [
        (index, fact, document)
        for index, fact in enumerate(facts)
        if fact.claim_date is not None
        for document in state.evidence
    ]
    answers = await asyncio.gather(
        *(_assess(deps, fact, document, validity) for _, fact, document in pairs)
    )
    assessed = [
        evidence.AssessedCitation(fact=index, draft=draft)
        for (index, _, _), (draft, _) in zip(pairs, answers, strict=True)
        if draft is not None
    ]
    usages = [model_usage(usage) for _, usage in answers]
    return state.model_copy(
        update={
            "claims": claims,
            "assessed": [*state.assessed, *assessed],
            "models": [*state.models, *usages],
        }
    )


async def _assess(
    deps: CheckDeps,
    fact: ExtractedClaim,
    document: SourceDocument,
    validity: dict[str, Validity],
) -> tuple[CitationDraft | None, LlmUsage]:
    claim_date = fact.claim_date or date.min  # filtered out by the caller
    entry_validity = validity.get(document.source.domain, "expires")
    return await evidence.assess_stance(
        deps.llm, fact.claim, claim_date, document, entry_validity
    )


def _claim_date(
    claim: ExtractedClaim, state: CheckState, today: date
) -> ExtractedClaim:
    if not claim.is_fact:
        return claim
    text_date = claim.claim_date if claim.claim_date_source == "text" else None
    resolved, source = evidence.resolve_check_claim_date(
        text_date, state.published_at, today=today
    )
    return claim.model_copy(
        update={"claim_date": resolved, "claim_date_source": source}
    )
