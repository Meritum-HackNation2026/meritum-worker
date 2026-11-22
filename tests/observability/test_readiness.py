"""The readiness report: missing variables, unreachable providers, names only."""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
from meritum_core.jobs.contracts import ReadinessReport

from meritum_worker.corpus import EuvsDisinfoUnavailableError
from meritum_worker.corpus.fakes import FakeEuvsDisinfoServer
from meritum_worker.observability import (
    build_readiness_probes,
    check_readiness,
    log_readiness,
)
from meritum_worker.observability.constants import LLM_REQUIRED_ENV, REQUIRED_ENV
from meritum_worker.observability.readiness import Probe, required_env

NOW = datetime(2026, 11, 22, tzinfo=UTC)
TOKEN = "euvs-token"  # ruff: ignore[hardcoded-password-string]  # a fake token
README = Path(__file__).resolve().parents[2] / "README.md"


async def _down() -> bool:  # ruff: ignore[unused-async]  # a Probe is awaited
    raise ConnectionError


def _check(
    env: dict[str, str], probes: dict[str, Probe] | None = None
) -> ReadinessReport:
    return asyncio.run(check_readiness(env, probes or {}, NOW))


def test_local_stub_worker_needs_nothing() -> None:
    assert required_env({"MERITUM_LLM_PROVIDER": "stub"}) == []


def test_demo_path_needs_only_the_database() -> None:
    report = _check({"MERITUM_ENV": "dev", "MERITUM_LLM_PROVIDER": "stub"})
    assert report.missing_env == ["MERITUM_DATABASE_URL"]


def test_openrouter_needs_its_key_even_locally() -> None:
    report = _check({"MERITUM_LLM_PROVIDER": "OpenRouter"})
    assert report.missing_env == ["OPENROUTER_API_KEY"]


def test_empty_variable_counts_as_missing() -> None:
    report = _check({"MERITUM_LLM_PROVIDER": "openrouter", "OPENROUTER_API_KEY": ""})
    assert report.missing_env == ["OPENROUTER_API_KEY"]


def test_probe_that_raises_is_an_unavailable_provider() -> None:
    report = _check({"MERITUM_LLM_PROVIDER": "stub"}, {"euvsdisinfo": _down})
    assert report.unavailable_providers == ["euvsdisinfo"]
    assert report.checked_at == NOW


@pytest.mark.parametrize(
    ("token", "unavailable"), [(TOKEN, []), ("wrong", ["euvsdisinfo"])]
)
def test_euvsdisinfo_probe_asks_the_server(token: str, unavailable: list[str]) -> None:
    server = FakeEuvsDisinfoServer(TOKEN)
    probes = build_readiness_probes({"EUVSDISINFO_MCP_API_KEY": token}, server.client())
    report = _check({"MERITUM_LLM_PROVIDER": "stub"}, probes)
    assert report.unavailable_providers == unavailable


def _fact_check_env(key: str | None) -> dict[str, str]:
    env = {"MERITUM_FACT_CHECK_PROVIDER": "google"}
    return env if key is None else {**env, "MERITUM_FACT_CHECK_API_KEY": key}


def _fact_check_probes(status: int, key: str | None) -> dict[str, Probe]:
    def reply(request: httpx2.Request) -> httpx2.Response:
        ok = request.headers.get("X-Goog-Api-Key") == "good-key"
        return httpx2.Response(status if ok else 403, json={})

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    return build_readiness_probes(_fact_check_env(key), client)


@pytest.mark.parametrize(
    ("status", "key", "unavailable"),
    [
        (200, "good-key", []),
        (200, "bad-key", ["fact_check"]),
        (200, None, ["fact_check"]),
        (429, "good-key", ["fact_check"]),
    ],
)
def test_fact_check_probe_degrades_on_bad_key_or_quota(
    status: int, key: str | None, unavailable: list[str]
) -> None:
    probes = _fact_check_probes(status, key)
    del probes["euvsdisinfo"]  # its own tests cover it
    report = _check({"MERITUM_LLM_PROVIDER": "stub", **_fact_check_env(key)}, probes)
    assert (report.missing_env, report.unavailable_providers) == ([], unavailable)


def test_stub_fact_check_has_no_probe() -> None:
    probes = build_readiness_probes({}, FakeEuvsDisinfoServer(TOKEN).client())
    assert "fact_check" not in probes


def test_missing_token_makes_euvsdisinfo_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probes = build_readiness_probes({}, FakeEuvsDisinfoServer(TOKEN).client())
    report = _check({"MERITUM_LLM_PROVIDER": "stub"}, probes)
    assert (report.missing_env, report.unavailable_providers) == ([], ["euvsdisinfo"])
    assert "MissingTokenError" in caplog.text


def test_log_names_variables_without_values(caplog: pytest.LogCaptureFixture) -> None:
    env = {"MERITUM_ENV": "prd", "MERITUM_LLM_PROVIDER": "openrouter"}
    report = _check(env | {"MERITUM_DATABASE_URL": "postgresql://secret"})
    log_readiness(report, logging.getLogger("t"))
    assert "OPENROUTER_API_KEY" in caplog.text
    assert "postgresql://secret" not in caplog.text


def test_readme_lists_every_required_variable() -> None:
    text = README.read_text(encoding="utf-8")
    names = {
        n
        for names in [*REQUIRED_ENV.values(), *LLM_REQUIRED_ENV.values()]
        for n in names
    }
    assert all(f"`{name}`" in text for name in names)


def test_empty_meritum_env_is_local() -> None:
    assert required_env({"MERITUM_ENV": "", "MERITUM_LLM_PROVIDER": "stub"}) == []


def test_unknown_model_provider_is_reported() -> None:
    report = _check({"MERITUM_LLM_PROVIDER": "nope"})
    assert report.missing_env == ["MERITUM_LLM_PROVIDER"]


async def _times_out() -> bool:  # ruff: ignore[unused-async]  # a Probe is awaited
    raise EuvsDisinfoUnavailableError(TOKEN) from TimeoutError


def test_failed_probe_logs_its_cause_without_the_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _check({"MERITUM_LLM_PROVIDER": "stub"}, {"euvsdisinfo": _times_out})
    assert "EuvsDisinfoUnavailableError from TimeoutError" in caplog.text
    assert TOKEN not in caplog.text


def test_unreachable_provider_only_degrades(caplog: pytest.LogCaptureFixture) -> None:
    report = _check({"MERITUM_LLM_PROVIDER": "stub"}, {"euvsdisinfo": _down})
    log_readiness(report, logging.getLogger("t"))
    assert "worker degraded" in caplog.text
    assert "not ready" not in caplog.text
