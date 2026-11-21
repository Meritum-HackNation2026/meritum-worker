"""Observability: the golden set, its validation and the evaluation run.

Features:
    US-OBS-04, US-OBS-05, F-27, US-WDR-08, US-BEZ-03, F-30
"""

from meritum_worker.observability.cases import load_eval_cases
from meritum_worker.observability.cli import meritum_eval
from meritum_worker.observability.errors import TooFewCasesError
from meritum_worker.observability.factory import build_readiness_probes
from meritum_worker.observability.golden import load_golden_set
from meritum_worker.observability.models import (
    CaseSource,
    GoldenCase,
    GoldenSet,
    Injection,
)
from meritum_worker.observability.outcomes import case_outcome, macro_f1
from meritum_worker.observability.readiness import (
    check_readiness,
    log_readiness,
)
from meritum_worker.observability.report import (
    CaseRun,
    CaseScore,
    EvalReport,
    ScenarioScore,
)
from meritum_worker.observability.runner import run_eval
from meritum_worker.observability.scoring import score_runs

__all__ = [
    "CaseRun",
    "CaseScore",
    "CaseSource",
    "EvalReport",
    "GoldenCase",
    "GoldenSet",
    "Injection",
    "ScenarioScore",
    "TooFewCasesError",
    "build_readiness_probes",
    "case_outcome",
    "check_readiness",
    "load_eval_cases",
    "load_golden_set",
    "log_readiness",
    "macro_f1",
    "meritum_eval",
    "run_eval",
    "score_runs",
]
