"""Builds the live gates of the comparison from their configurations.

Features:
    US-BEZ-01, US-BEZ-04, F-27, ADR-35
"""

from meritum_core.security.injection import InjectionGatePort
from meritum_core.security.pii import PiiGatePort, PiiGateSettings, build_pii_gate

from meritum_worker.observability.gates.compare import GateBuilders
from meritum_worker.observability.gates.models import DlpConfig, InjectionConfig
from meritum_worker.security import InjectionGateSettings, build_injection_gate


def build_gate_builders() -> GateBuilders:
    """Gates from the worker and core factories; secrets come from the environment.

    Returns:
        The builders.

    Features:
        US-BEZ-01, US-BEZ-04, F-27, ADR-35
    """
    return GateBuilders(injection=_injection, pii=_pii)


def _injection(config: InjectionConfig) -> InjectionGatePort:
    return build_injection_gate(InjectionGateSettings.model_validate(config.settings))


def _pii(config: DlpConfig) -> PiiGatePort:
    return build_pii_gate(PiiGateSettings.model_validate(config.settings))
