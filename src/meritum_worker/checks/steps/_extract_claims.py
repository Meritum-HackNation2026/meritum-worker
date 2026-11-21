"""Extract up to 5 dated claims and tell facts from opinions and predictions.

Features:
    US-SPR-03, US-SPR-06, US-ZRD-05, F-07
"""

from datetime import date

from meritum_core.shared.llm import Prompt

from meritum_worker.checks.constants import (
    EXTRACTION_INSTRUCTIONS,
    LIMITATION_MAX_CHARS,
    MAX_CLAIMS_PER_CHECK,
    NEEDS_CLARIFICATION_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
)
from meritum_worker.checks.models import (
    CheckDeps,
    CheckState,
    ClaimExtraction,
    ExtractedClaim,
    model_usage,
)


async def extract_claims(state: CheckState, deps: CheckDeps) -> CheckState:
    """Ask the model for the input's claims; the user text goes only as data.

    A request not about information ends as out_of_scope and an input with no
    claim as needs_clarification, both with a message and no claims. Otherwise
    facts come first, the first MAX_CLAIMS_PER_CHECK go on with a date each and
    the rest are named in the limitations.

    Args:
        state: the check so far; a state that already has a result passes on.
        deps: the ports; only the model is called.

    Returns:
        The state with its claims and limitations, or with a result that is not
        a verdict.

    A model failure propagates; the workflow maps it to technical_failure.

    Features:
        US-SPR-03, US-SPR-06, US-ZRD-05, F-07
    """
    if state.result is not None:
        return state
    prompt = Prompt(instructions=EXTRACTION_INSTRUCTIONS, data=(state.question,))
    answer = await deps.llm.complete(prompt, ClaimExtraction)
    state = state.model_copy(
        update={"models": [*state.models, model_usage(answer.usage)]}
    )
    extraction = answer.output
    if extraction.out_of_scope:
        result = state.with_message("out_of_scope", OUT_OF_SCOPE_MESSAGE)
        return state.model_copy(update={"result": result})
    if not extraction.claims:
        result = state.with_message("needs_clarification", NEEDS_CLARIFICATION_MESSAGE)
        return state.model_copy(update={"result": result})
    # sorted() is stable: facts first, each group in the order of the input.
    ranked = sorted(extraction.claims, key=lambda claim: not claim.is_fact)
    kept = ranked[:MAX_CLAIMS_PER_CHECK]
    skipped = ranked[MAX_CLAIMS_PER_CHECK:]
    today = state.job.received_at.date()
    return state.model_copy(
        update={
            "claims": [_dated(claim, today) for claim in kept],
            "limitations": [*state.limitations, *map(_skipped_note, skipped)],
        }
    )


def _dated(claim: ExtractedClaim, today: date) -> ExtractedClaim:
    # A date the model did not find in the text is the day the check came in.
    if claim.claim_date is None:
        return claim.model_copy(
            update={"claim_date": today, "claim_date_source": "today"}
        )
    return claim.model_copy(
        update={"claim_date_source": claim.claim_date_source or "text"}
    )


def _skipped_note(claim: ExtractedClaim) -> str:
    return claim.claim[:LIMITATION_MAX_CHARS]
