"""Builds the ports of the `check` workflow; nothing else instantiates adapters.

Features:
    US-SPR-01, US-OBS-01, F-22, ADR-03
"""

from meritum_core.corpus.fetching import build_page_fetcher
from meritum_core.observability import build_app_repositories
from meritum_core.security.pii import PiiGateSettings, build_pii_gate
from meritum_core.shared.database import DatabaseSettings
from meritum_core.shared.llm import LlmSettings, build_llm

from meritum_worker.checks.adapters import DbosCheckRuntime
from meritum_worker.checks.models import CheckDeps
from meritum_worker.checks.ports import CheckRuntime


def build_check_deps(settings: LlmSettings, database: DatabaseSettings) -> CheckDeps:
    """Build the model, the record repository, the page fetcher and the masking gate.

    Args:
        settings: LLM settings, usually ``LlmSettings()`` from ``MERITUM_LLM_*``.
        database: app database settings, usually ``DatabaseSettings()`` from
            ``MERITUM_DATABASE_*``: in-memory fakes by default, PostgreSQL on dev
            and prd.

    Returns:
        The ports.

    Features:
        US-SPR-01, US-SPR-07, US-OBS-01, F-06, F-22
    """
    records = build_app_repositories(database).records
    return CheckDeps(
        llm=build_llm(settings),
        records=records,
        pages=build_page_fetcher(),
        pii=build_pii_gate(PiiGateSettings()),
    )


def build_check_runtime() -> CheckRuntime:
    """Build the DBOS runtime; call it inside the `check` workflow.

    Returns:
        The runtime.

    Features:
        US-SPR-01, F-22, ADR-03
    """
    return DbosCheckRuntime()
