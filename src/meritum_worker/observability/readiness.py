"""The `readiness` report: which variables and providers the worker lacks.

Features:
    US-WDR-08, US-BEZ-03, F-30
"""

import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime

from meritum_core.jobs.contracts import ReadinessReport
from meritum_core.shared.llm import LlmSettings

from meritum_worker.observability.constants import (
    DEMO_PATH,
    ENV_NAME_VAR,
    LLM_PROVIDER_VAR,
    LLM_REQUIRED_ENV,
    LOCAL_ENV,
    REQUIRED_ENV,
)

_log = logging.getLogger(__name__)

type Probe = Callable[[], Awaitable[bool]]
"""Says whether one provider answers; a free call where the provider has one."""


def required_env(env: Mapping[str, str]) -> list[str]:
    """Name the variables this worker's path and model provider need.

    Args:
        env: The worker's environment, usually ``os.environ``.

    Returns:
        The names, in a stable order.

    Features:
        US-WDR-08, F-30
    """
    path = LOCAL_ENV if (env.get(ENV_NAME_VAR) or LOCAL_ENV) == LOCAL_ENV else DEMO_PATH
    default = str(LlmSettings.model_fields["provider"].default)
    provider = (env.get(LLM_PROVIDER_VAR) or default).lower()
    if provider not in LLM_REQUIRED_ENV:
        # An unknown provider fails every check, so the report names its variable.
        return [*REQUIRED_ENV[path], LLM_PROVIDER_VAR]
    return [*REQUIRED_ENV[path], *LLM_REQUIRED_ENV[provider]]


async def check_readiness(
    env: Mapping[str, str], probes: Mapping[str, Probe], now: datetime
) -> ReadinessReport:
    """Check the variables, then ask each provider whether it answers.

    Args:
        env: The worker's environment, usually ``os.environ``.
        probes: One probe per provider whose variables are set.
        now: The time of the check.

    Returns:
        The report; a probe that raises counts as an unavailable provider.

    Features:
        US-WDR-08, US-BEZ-03, F-30
    """
    known = LLM_REQUIRED_ENV.keys()
    missing = [
        name
        for name in required_env(env)
        if not env.get(name, "")
        or (name == LLM_PROVIDER_VAR and env[name].lower() not in known)
    ]
    unavailable = [name for name, probe in probes.items() if not await _answers(probe)]
    return ReadinessReport(
        missing_env=missing, unavailable_providers=unavailable, checked_at=now
    )


async def _answers(probe: Probe) -> bool:
    try:
        return await probe()
    except Exception as error:  # ruff: ignore[blind-except]  # a broken provider is reported, never crashes
        # The type only: a message could quote the token.
        _log.warning("readiness probe failed: %s", type(error).__name__)
        return False


def log_readiness(report: ReadinessReport, logger: logging.Logger) -> None:
    """Log the report's names only; values of secrets never reach the log.

    Args:
        report: The report from ``check_readiness``.
        logger: The worker's logger.

    Features:
        US-WDR-08, US-BEZ-03, F-30
    """
    if report.missing_env or report.unavailable_providers:
        logger.warning(
            "worker not ready: missing env %s, unavailable providers %s",
            report.missing_env,
            report.unavailable_providers,
        )
    else:
        logger.info("worker ready: no missing env, all providers answer")
