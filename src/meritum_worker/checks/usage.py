"""The usage entry the CheckRecord keeps for one model call.

Features:
    US-OBS-01, F-22
"""

from meritum_core.checks.contracts import ModelUsage
from meritum_core.shared.llm import LlmUsage


def model_usage(usage: LlmUsage) -> ModelUsage:
    """Turn one LLM call's usage into the ModelUsage the CheckRecord keeps.

    Cost stays 0 until the cost step prices the call (worker#26).

    Args:
        usage: provider, model, region and tokens of the call.

    Returns:
        The usage entry.

    Features:
        US-OBS-01, F-22
    """
    return ModelUsage(
        provider=usage.provider,
        model=usage.model,
        region=usage.region,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=0.0,
    )
