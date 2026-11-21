"""Builds the ports an evaluation run checks cases on.

Features:
    US-OBS-04, US-OBS-05, F-27, ADR-28
"""

from dataclasses import replace

from meritum_core.shared.database import DatabaseProvider, DatabaseSettings
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import CheckDeps
from meritum_worker.checks.factory import build_check_deps
from meritum_worker.observability.models import GoldenCase
from meritum_worker.observability.runner import DepsFor


def build_eval_deps(settings: LlmSettings) -> DepsFor:
    """Ports on the model from ``MERITUM_LLM_*`` and in-memory records.

    Records stay in memory, so a run never writes to the app database. A case
    with ``fault: llm`` gets a stub model without answers, which fails like
    an unavailable provider.

    Args:
        settings: The model to evaluate.

    Returns:
        The ports per case.

    Features:
        US-OBS-04, US-OBS-05, F-27, ADR-28
    """
    deps = build_check_deps(
        settings, DatabaseSettings(provider=DatabaseProvider.MEMORY)
    )
    # Explicit None: the environment's stub fixtures must not reach this model.
    no_answers = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=None)
    broken = replace(deps, llm=build_llm(no_answers))

    def deps_for(case: GoldenCase) -> CheckDeps:
        return broken if case.fault == "llm" else deps

    return deps_for
