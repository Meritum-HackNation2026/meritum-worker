"""Builds the classifier gate named by configuration and the detector around it.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-35
"""

from google.auth.credentials import Credentials
from httpx2 import AsyncClient
from meritum_core.security.injection import (
    InjectionDetectorPort,
    InjectionGatePort,
    NullInjectionGate,
    build_injection_detector,
)
from meritum_core.shared.llm import LlmPort

from meritum_worker.security.adapters import ModelArmorGate, WorkersAiGate
from meritum_worker.security.settings import (
    InjectionGateProvider,
    InjectionGateSettings,
)


def build_injection_gate(
    settings: InjectionGateSettings,
    *,
    credentials: Credentials | None = None,
    http_client: AsyncClient | None = None,
) -> InjectionGatePort:
    """Build the gate the settings name.

    Args:
        settings: Usually ``InjectionGateSettings()`` from the environment.
        credentials: Google credentials for Model Armor; Application Default
            Credentials when None. Ignored by the other gates.
        http_client: HTTP client (shared pool, or recorded replies in tests); a
            new one when None. Ignored by the null gate.

    Returns:
        Model Armor, Workers AI, or the null gate when no provider is set.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-35
    """
    match settings.provider:
        case InjectionGateProvider.MODEL_ARMOR:
            return ModelArmorGate(
                settings, credentials=credentials, http_client=http_client
            )
        case InjectionGateProvider.WORKERS_AI:
            return WorkersAiGate(settings, http_client=http_client)
        case InjectionGateProvider.NONE:
            return NullInjectionGate()


def build_detector(
    llm: LlmPort,
    settings: InjectionGateSettings,
    *,
    credentials: Credentials | None = None,
    http_client: AsyncClient | None = None,
) -> InjectionDetectorPort:
    """Build core's layered detector with the configured gate (ADR-12, ADR-35).

    Args:
        llm: The model of the isolated classifier layer.
        settings: Gate settings, usually ``InjectionGateSettings()``.
        credentials: Passed to ``build_injection_gate``.
        http_client: Passed to ``build_injection_gate``.

    Returns:
        Patterns, the configured gate and the isolated LLM classifier.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-23, ADR-35
    """
    gate = build_injection_gate(
        settings, credentials=credentials, http_client=http_client
    )
    return build_injection_detector(llm=llm, gate=gate)
