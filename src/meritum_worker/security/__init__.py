"""Injection classifier gate of the worker: provider adapters behind core's port.

Public API: settings, the gate factory and the detector factory.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-35
"""

from meritum_worker.security.factory import build_detector, build_injection_gate
from meritum_worker.security.settings import (
    InjectionGateProvider,
    InjectionGateSettings,
)

__all__ = [
    "InjectionGateProvider",
    "InjectionGateSettings",
    "build_detector",
    "build_injection_gate",
]
