"""Steps for the readiness scenarios of features/deploy.feature, on fake probes."""

import asyncio
import logging
from datetime import UTC, datetime
from logging.handlers import BufferingHandler

from behave import given, then, when
from behave.runner import Context

from meritum_worker.observability import check_readiness, log_readiness

SECRET = "s3cret-value"  # ruff: ignore[hardcoded-password-string]  # a fake token
NOW = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)
DEMO_ENV = {
    "MERITUM_ENV": "prd",
    "MERITUM_LLM_PROVIDER": "stub",
    "MERITUM_DATABASE_URL": "postgresql://db/app",
    "EUVSDISINFO_MCP_API_KEY": SECRET,
}


async def _reachable() -> bool:  # ruff: ignore[unused-async]  # a Probe is awaited
    return True


@given("worker startuje bez zmiennej z tokenem EUvsDisinfo")
def without_euvs_token(context: Context) -> None:
    context.env = {k: v for k, v in DEMO_ENV.items() if k != "EUVSDISINFO_MCP_API_KEY"}


@given("wszystkie wymagane zmienne i dostępni dostawcy")
def everything_set(context: Context) -> None:
    context.env = dict(DEMO_ENV)


@when("kończy sprawdzanie gotowości")
@when("worker publikuje raport")
def readiness_runs(context: Context) -> None:
    probes = {"euvsdisinfo": _reachable}
    context.report = asyncio.run(check_readiness(context.env, probes, NOW))
    handler = BufferingHandler(capacity=100)
    logger = logging.getLogger("readiness-test")
    logger.addHandler(handler)
    log_readiness(context.report, logger)
    logger.removeHandler(handler)
    context.log = "\n".join(r.getMessage() for r in handler.buffer)


@then(
    "raport wymienia nazwę brakującej zmiennej, a log startu ma tę samą listę "
    "bez wartości sekretów"
)
def report_names_the_token(context: Context) -> None:
    assert context.report.missing_env == ["EUVSDISINFO_MCP_API_KEY"]
    assert "EUVSDISINFO_MCP_API_KEY" in context.log
    assert "postgresql://db/app" not in context.log


@then("raport nie ma braków i ma czas sprawdzenia")
def report_is_clean(context: Context) -> None:
    assert context.report.missing_env == []
    assert context.report.unavailable_providers == []
    assert context.report.checked_at == NOW
    assert SECRET not in context.log
