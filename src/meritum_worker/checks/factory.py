"""Builds the ports of the `check` workflow; nothing else instantiates adapters.

Features:
    US-SPR-01, US-OBS-01, F-22, ADR-03
"""

from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.shared.llm import LlmSettings, build_llm

from meritum_worker.checks.adapters import DbosCheckRuntime
from meritum_worker.checks.models import CheckDeps
from meritum_worker.checks.ports import CheckRuntime


def build_check_deps(settings: LlmSettings) -> CheckDeps:
    """Build the model and the record repository the steps call.

    Args:
        settings: LLM settings, usually ``LlmSettings()`` from ``MERITUM_LLM_*``.

    Returns:
        The ports.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    # shortcut: records live in memory and die with the process; switch to the
    # PostgreSQL repository once meritum-core#38 ships it.
    return CheckDeps(llm=build_llm(settings), records=InMemoryCheckRecordRepository())


def build_check_runtime() -> CheckRuntime:
    """Build the DBOS runtime; call it inside the `check` workflow.

    Returns:
        The runtime.

    Features:
        US-SPR-01, F-22, ADR-03
    """
    return DbosCheckRuntime()
