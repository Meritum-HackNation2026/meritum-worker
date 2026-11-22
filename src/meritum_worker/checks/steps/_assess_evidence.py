"""Set evidence validity and compute verdict rules at the claim date.

Stance assessment per citation lands in worker#34; here each verified citation gets
its validity from core, and facts without stance yet keep the state unchanged.

Features:
    US-ZRD-04, US-ZRD-05, US-ZRD-10, US-SPR-01, US-OBS-01, F-15, F-22
"""

from datetime import date

from meritum_worker import evidence
from meritum_worker.checks.models import CheckDeps, CheckState, ExtractedClaim


async def assess_evidence(state: CheckState, deps: CheckDeps) -> CheckState:
    """Apply core#41 rules to verified citations and normalize claim dates.

    Each fact's date is fixed with ``resolve_claim_date``. Citations already on
    the state get ``assign_validity`` at that date. Verdict and strength for the
    check are derived later from the judged citations in tests or in write_answer
    once worker#34 adds stances.

    Args:
        state: the check so far.
        deps: the ports; the catalogue supplies ``max_age_hours``.

    Returns:
        The state with claim dates and citation validities updated.

    Features:
        US-ZRD-04, US-ZRD-05, US-ZRD-10, US-SPR-01, US-OBS-01, F-15, F-22
    """
    if state.result is not None:
        return state
    today = state.job.received_at.date()
    claims = [_claim_date(claim, state, today) for claim in state.claims]
    if not state.citations:
        if claims == state.claims:
            return state
        return state.model_copy(update={"claims": claims})
    catalog = {entry.domain: entry for entry in deps.catalog}
    facts = [claim for claim in claims if claim.is_fact]
    updated: list[evidence.VerifiedCitation] = []
    for verified in state.citations:
        if verified.fact >= len(facts):
            continue
        fact = facts[verified.fact]
        if fact.claim_date is None:
            continue
        dated = evidence.with_validity(
            [verified.citation], catalog, claim_date=fact.claim_date
        )
        updated.append(evidence.VerifiedCitation(fact=verified.fact, citation=dated[0]))
    return state.model_copy(update={"claims": claims, "citations": updated})


def _claim_date(
    claim: ExtractedClaim, state: CheckState, today: date
) -> ExtractedClaim:
    if not claim.is_fact:
        return claim
    text_date = claim.claim_date if claim.claim_date_source == "text" else None
    resolved, source = evidence.resolve_check_claim_date(
        text_date, state.published_at, today=today
    )
    if claim.claim_date == resolved and claim.claim_date_source == source:
        return claim
    return claim.model_copy(
        update={"claim_date": resolved, "claim_date_source": source}
    )
