"""Gate comparison: injection classifier, reranker, DLP, NLI and input classifier.

Public API: configurations, the comparison, scoring on recorded calls and the
``meritum-eval gates`` command (ADR-35).

Features:
    US-BEZ-01, US-OBS-04, F-27, ADR-35
"""

from meritum_worker.observability.gates.cli import gates_eval
from meritum_worker.observability.gates.compare import (
    GateBuilders,
    compare_gates,
    load_gate_config,
)
from meritum_worker.observability.gates.constants import GATES_COMMAND
from meritum_worker.observability.gates.models import (
    DlpCase,
    GateCall,
    GateModel,
    StanceCall,
)
from meritum_worker.observability.gates.report import GatesReport
from meritum_worker.observability.gates.runner import mask_cases, screen_cases
from meritum_worker.observability.gates.scoring import (
    reranker_delta,
    score_classifier,
    score_dlp,
    score_injection,
    score_nli,
)

__all__ = [
    "GATES_COMMAND",
    "DlpCase",
    "GateBuilders",
    "GateCall",
    "GateModel",
    "GatesReport",
    "StanceCall",
    "compare_gates",
    "gates_eval",
    "load_gate_config",
    "mask_cases",
    "reranker_delta",
    "score_classifier",
    "score_dlp",
    "score_injection",
    "score_nli",
    "screen_cases",
]
