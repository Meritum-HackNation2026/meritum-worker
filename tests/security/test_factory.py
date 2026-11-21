"""Gate settings and factory: provider from configuration, null gate by default."""

import pytest
from meritum_core.security.injection import NullInjectionGate
from pydantic import ValidationError

from meritum_worker.security import (
    InjectionGateProvider,
    InjectionGateSettings,
    build_injection_gate,
)


def test_no_configuration_builds_the_null_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MERITUM_INJECTION_GATE_PROVIDER", raising=False)
    assert isinstance(build_injection_gate(InjectionGateSettings()), NullInjectionGate)


def test_provider_and_account_come_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MERITUM_INJECTION_GATE_PROVIDER", "workers_ai")
    monkeypatch.setenv("MERITUM_INJECTION_GATE_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("MERITUM_INJECTION_GATE_API_TOKEN", "cf-token")
    monkeypatch.setenv("MERITUM_INJECTION_GATE_MODEL", "@cf/meta/llama-guard-3-8b")
    settings = InjectionGateSettings()
    assert settings.provider is InjectionGateProvider.WORKERS_AI
    assert "cf-token" not in repr(settings)


@pytest.mark.parametrize(
    ("provider", "missing"),
    [
        (InjectionGateProvider.MODEL_ARMOR, "MERITUM_INJECTION_GATE_TEMPLATE"),
        (InjectionGateProvider.WORKERS_AI, "MERITUM_INJECTION_GATE_API_TOKEN"),
    ],
)
def test_provider_without_its_settings_is_rejected(
    provider: InjectionGateProvider, missing: str
) -> None:
    with pytest.raises(ValidationError, match=missing):
        InjectionGateSettings(provider=provider, project="p", account_id="a", model="m")
