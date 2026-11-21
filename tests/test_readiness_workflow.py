"""The worker's readiness body reads the real environment and never raises."""

import asyncio

import pytest

from meritum_worker import main


def test_readiness_reports_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERITUM_ENV", "dev")
    monkeypatch.setenv("MERITUM_LLM_PROVIDER", "openrouter")
    for name in ("EUVSDISINFO_MCP_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    report = asyncio.run(main.readiness_report())
    assert "EUVSDISINFO_MCP_API_KEY" in report["missing_env"]
    assert "OPENROUTER_API_KEY" in report["missing_env"]
    assert report["unavailable_providers"] == []
