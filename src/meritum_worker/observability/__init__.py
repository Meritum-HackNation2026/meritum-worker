"""Observability: the golden set, its validation and the evaluation run.

Features:
    US-OBS-04, US-OBS-05, US-OBS-06, US-OBS-07, F-27, F-28, US-WDR-08, US-BEZ-03, F-30
"""

from meritum_worker.observability.bundle import Manifest, meritum_eval_bundle
from meritum_worker.observability.cases import load_eval_cases
from meritum_worker.observability.cassette import Cassette, EvalMode, LlmTake, PageTake
from meritum_worker.observability.cli import meritum_eval
from meritum_worker.observability.comparison import (
    ComparedModel,
    ModelComparison,
    ModelConfig,
    compare_models,
    load_model_config,
)
from meritum_worker.observability.constants import (
    DEFAULT_CASES_FILE,
    DEFAULT_EVAL_FILES_DIR,
    EVAL_FILES_DIR_VAR,
)
from meritum_worker.observability.errors import CassetteMissError, TooFewCasesError
from meritum_worker.observability.eval_run import (
    EvalRunDeps,
    evaluate_eval_run,
    finish_eval_run,
    run_eval_run,
    start_eval_run,
)
from meritum_worker.observability.factory import (
    build_eval_run_deps,
    build_readiness_probes,
)
from meritum_worker.observability.golden import load_golden_set
from meritum_worker.observability.models import (
    CaseSource,
    GoldenCase,
    GoldenSet,
    Injection,
)
from meritum_worker.observability.outcomes import case_outcome, macro_f1
from meritum_worker.observability.ports import EvalCaseSets, EvalRunRepository
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
from meritum_worker.observability.retrieval import (
    EmbeddingsComparison,
    EmbeddingsConfig,
    RetrievalScore,
    compare_embeddings,
    load_embeddings_config,
    score_retrieval,
)
from meritum_worker.observability.run_comparison import (
    ChangedCase,
    MetricChange,
    RunComparison,
    compare_runs,
)
from meritum_worker.observability.runner import run_eval
from meritum_worker.observability.scoring import score_runs

__all__ = [
    "DEFAULT_CASES_FILE",
    "DEFAULT_EVAL_FILES_DIR",
    "EVAL_FILES_DIR_VAR",
    "CaseRun",
    "CaseScore",
    "CaseSource",
    "Cassette",
    "CassetteMissError",
    "ChangedCase",
    "ComparedModel",
    "EmbeddingsComparison",
    "EmbeddingsConfig",
    "EvalCaseSets",
    "EvalMode",
    "EvalReport",
    "EvalRunDeps",
    "EvalRunRepository",
    "GoldenCase",
    "GoldenSet",
    "Injection",
    "LlmTake",
    "Manifest",
    "MetricChange",
    "ModelComparison",
    "ModelConfig",
    "PageTake",
    "RetrievalScore",
    "RunComparison",
    "ScenarioScore",
    "TooFewCasesError",
    "build_eval_run_deps",
    "build_readiness_probes",
    "case_outcome",
    "check_readiness",
    "compare_embeddings",
    "compare_models",
    "compare_runs",
    "evaluate_eval_run",
    "finish_eval_run",
    "load_embeddings_config",
    "load_eval_cases",
    "load_golden_set",
    "load_model_config",
    "log_readiness",
    "macro_f1",
    "meritum_eval",
    "meritum_eval_bundle",
    "run_eval",
    "run_eval_run",
    "score_retrieval",
    "score_runs",
    "start_eval_run",
]
