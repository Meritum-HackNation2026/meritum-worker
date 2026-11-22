"""Write the answer with the model and hold it to the CheckResult rules.

Features:
    US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, US-BEZ-07, F-07, F-22
"""

from datetime import UTC, datetime

from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import ClaimResult, ModelUsage, ai_marker_for
from meritum_core.shared.llm import Prompt
from pydantic import ValidationError

from meritum_worker.checks.constants import ANSWER_INSTRUCTIONS
from meritum_worker.checks.models import (
    AnswerDraft,
    CheckDeps,
    CheckState,
    ExtractedClaim,
)
from meritum_worker.checks.usage import model_usage


async def write_answer(state: CheckState, deps: CheckDeps) -> CheckState:
    """Ask the model to answer the extracted facts; a rule break is a failure.

    Opinions and predictions get "not_verifiable" without the model's verdict.
    Each answered fact keeps its text and date from extraction. With no fact
    the model writes only the limitations.

    Args:
        state: the check so far; a state that already has a result passes on.
        deps: the ports; only the model is called.

    Returns:
        The state with the result: done with the AI marker of the answering call,
        or technical_failure without claims when the answer breaks the contract
        rules.

    A model failure propagates; the workflow maps it to technical_failure.

    Features:
        US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, US-BEZ-07, F-07, F-22
    """
    if state.result is not None:
        return state
    facts = [claim for claim in state.claims if claim.is_fact]
    data = (state.question, *(fact.claim for fact in facts))
    prompt = Prompt(instructions=ANSWER_INSTRUCTIONS, data=data)
    answer = await deps.llm.complete(prompt, AnswerDraft)
    usage = model_usage(answer.usage)
    models = [*state.models, usage]
    try:
        result = _result_from_draft(state, facts, answer.output, usage)
    except ValidationError:
        result = state.technical_failure()
    return state.model_copy(update={"result": result, "models": models})


def _result_from_draft(
    state: CheckState,
    facts: list[ExtractedClaim],
    draft: AnswerDraft,
    usage: ModelUsage,
) -> CheckResult:
    if not facts:
        # Only opinions: nothing for the model to judge, whatever it answered.
        draft = draft.model_copy(update={"claims": []})
    if len(draft.claims) != len(facts):
        # One result per fact, or the answer cannot be tied to its claims.
        return state.technical_failure()
    answered = list(map(_answered, facts, draft.claims, strict=True))
    unverifiable = [_not_verifiable(c) for c in state.claims if not c.is_fact]
    return CheckResult(
        check_id=state.check_id,
        status="done",
        claims=[*answered, *unverifiable],
        limitations=[*draft.limitations, *state.limitations],
        corpus_version=state.corpus_version,
        ai_marker=ai_marker_for(usage, datetime.now(UTC)),
    )


def _answered(fact: ExtractedClaim, claim: ClaimResult) -> ClaimResult:
    return ClaimResult.model_validate(
        {
            **claim.model_dump(),
            "claim": fact.claim,
            "claim_date": fact.claim_date,
            "claim_date_source": fact.claim_date_source,
        }
    )


def _not_verifiable(claim: ExtractedClaim) -> ClaimResult:
    # extract_claims dated every claim; the contract rejects one it did not.
    return ClaimResult.model_validate(
        {
            "claim": claim.claim,
            "claim_date": claim.claim_date,
            "claim_date_source": claim.claim_date_source,
            "verdict": "not_verifiable",
            "explanation": claim.explanation,
        }
    )
