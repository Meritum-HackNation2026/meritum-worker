"""The meritum-eval command: one run or a model comparison, the report as JSON.

Features:
    US-OBS-04, US-OBS-05, US-WDR-02, F-27, ADR-28
"""

import argparse
import asyncio
import csv
import sys
import tomllib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from meritum_core.shared.embeddings import build_embeddings
from meritum_core.shared.llm import LlmSettings
from pydantic import BaseModel, ValidationError

from meritum_worker.observability.cases import load_eval_cases
from meritum_worker.observability.comparison import compare_models, load_model_config
from meritum_worker.observability.constants import (
    DEFAULT_CASES_FILE,
    DEFAULT_MAX_CONCURRENCY,
    EVAL_NAME,
)
from meritum_worker.observability.factory import build_eval_deps
from meritum_worker.observability.models import GoldenSet
from meritum_worker.observability.retrieval import (
    compare_embeddings,
    load_embeddings_config,
    score_retrieval,
)
from meritum_worker.observability.runner import run_eval
from meritum_worker.observability.scoring import score_runs


def meritum_eval(argv: Sequence[str] | None = None) -> None:
    """Evaluate the model from ``MERITUM_LLM_*``, or compare config files.

    Args:
        argv: Command-line arguments; ``sys.argv`` when None.

    Features:
        US-OBS-04, US-OBS-05, US-WDR-02, F-27, ADR-28
    """
    parser = argparse.ArgumentParser(prog=EVAL_NAME)
    parser.add_argument("--cases", type=Path, default=Path(DEFAULT_CASES_FILE))
    parser.add_argument(
        "--max-concurrency", type=_positive, default=DEFAULT_MAX_CONCURRENCY
    )
    parser.add_argument("--output", type=Path, help="report file; stdout without it")
    compare = parser.add_mutually_exclusive_group()
    compare.add_argument(
        "--compare-models", nargs="+", type=Path, metavar="CONFIG", default=[]
    )
    compare.add_argument(
        "--compare-embeddings", nargs="+", type=Path, metavar="CONFIG", default=[]
    )
    args = parser.parse_args(argv)
    try:
        cases = load_eval_cases(args.cases)
    except (OSError, TypeError, ValueError, csv.Error) as error:
        # Too few cases, bad JSON or an invalid case: a message, not a traceback.
        parser.error(f"{args.cases}: {error}")
    try:
        report = asyncio.run(
            _report(
                cases,
                args.cases,
                args.compare_models,
                args.compare_embeddings,
                args.max_concurrency,
            )
        )
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        parser.error(f"config: {error}")
    text = report.model_dump_json(indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.write_text(text, encoding="utf-8")


async def _report(
    cases: GoldenSet,
    cases_file: Path,
    models: Sequence[Path],
    embeddings: Sequence[Path],
    concurrency: int,
) -> BaseModel:
    now = datetime.now(UTC)
    if models:
        # Load every file first, so a typo fails before any model is paid for.
        configs = [load_model_config(path) for path in models]
        entries = [
            (c, await run_eval(cases, build_eval_deps(c.llm), concurrency))
            for c in configs
        ]
        return compare_models(entries, str(cases_file), now)
    if embeddings:
        embedding_configs = [load_embeddings_config(path) for path in embeddings]
        scores = [
            await score_retrieval(cases, c, build_embeddings(c.embeddings))
            for c in embedding_configs
        ]
        return compare_embeddings(scores, str(cases_file), now)
    deps_for = build_eval_deps(LlmSettings())
    return score_runs(await run_eval(cases, deps_for, concurrency))


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        msg = f"must be at least 1, got {number}"
        raise argparse.ArgumentTypeError(msg)
    return number
