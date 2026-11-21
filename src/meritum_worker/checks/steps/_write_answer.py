"""Write the answer with the model and hold it to the CheckResult rules.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import ModelUsage
from meritum_core.shared.llm import LlmUsage, Prompt, ProviderUnavailableError
from pydantic import ValidationError

from meritum_worker.checks.constants import ANSWER_INSTRUCTIONS
from meritum_worker.checks.models import AnswerDraft, CheckDeps, CheckState


async def write_answer(state: CheckState, deps: CheckDeps) -> CheckState:
    """Ask the model for the answer; a failed call or a rule break is a failure.

    Args:
        state: the check so far.
        deps: the ports; only the model is called.

    Returns:
        The state with the result: done, or technical_failure without claims
        when the provider fails or the answer breaks the contract rules.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    prompt = Prompt(instructions=ANSWER_INSTRUCTIONS, data=(state.question,))
    try:
        answer = await deps.llm.complete(prompt, AnswerDraft)
    except ProviderUnavailableError:
        return state.model_copy(update={"result": state.technical_failure()})
    models = [*state.models, _usage(answer.usage)]
    try:
        result = CheckResult(
            check_id=state.check_id,
            status="done",
            claims=answer.output.claims,
            limitations=answer.output.limitations,
            corpus_version=state.corpus_version,
        )
    except ValidationError:
        result = state.technical_failure()
    return state.model_copy(update={"result": result, "models": models})


def _usage(usage: LlmUsage) -> ModelUsage:
    # Cost stays 0 until the cost step prices the call (worker#26).
    return ModelUsage(
        provider=usage.provider,
        model=usage.model,
        region=usage.region,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=0.0,
    )
