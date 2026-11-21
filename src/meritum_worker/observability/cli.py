"""The meritum-eval command: one run on a case file, the report as JSON.

Features:
    US-OBS-04, US-OBS-05, F-27, ADR-28
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from meritum_core.shared.llm import LlmSettings

from meritum_worker.observability.cases import load_eval_cases
from meritum_worker.observability.constants import (
    DEFAULT_CASES_FILE,
    DEFAULT_MAX_CONCURRENCY,
    EVAL_NAME,
)
from meritum_worker.observability.factory import build_eval_deps
from meritum_worker.observability.runner import run_eval
from meritum_worker.observability.scoring import score_runs


def meritum_eval(argv: Sequence[str] | None = None) -> None:
    """Evaluate the model from ``MERITUM_LLM_*`` on a case file.

    Args:
        argv: Command-line arguments; ``sys.argv`` when None.

    Features:
        US-OBS-04, US-OBS-05, F-27, ADR-28
    """
    parser = argparse.ArgumentParser(prog=EVAL_NAME)
    parser.add_argument("--cases", type=Path, default=Path(DEFAULT_CASES_FILE))
    parser.add_argument(
        "--max-concurrency", type=_positive, default=DEFAULT_MAX_CONCURRENCY
    )
    parser.add_argument("--output", type=Path, help="report file; stdout without it")
    args = parser.parse_args(argv)
    try:
        cases = load_eval_cases(args.cases)
    except (OSError, ValueError) as error:
        # Too few cases, bad JSON or an invalid case: a message, not a traceback.
        parser.error(f"{args.cases}: {error}")
    deps_for = build_eval_deps(LlmSettings())
    runs = asyncio.run(run_eval(cases, deps_for, args.max_concurrency))
    report = score_runs(runs).model_dump_json(indent=2)
    if args.output is None:
        sys.stdout.write(report + "\n")
    else:
        args.output.write_text(report + "\n", encoding="utf-8")


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        msg = f"must be at least 1, got {number}"
        raise argparse.ArgumentTypeError(msg)
    return number
