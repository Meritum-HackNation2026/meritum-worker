"""The meritum-eval command: one run or a model comparison, the report as JSON.

Features:
    US-OBS-04, US-OBS-05, US-OBS-07, US-WDR-02, F-27, ADR-28
"""

import argparse
import asyncio
import csv
import sys
import tomllib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from meritum_core.corpus import CorpusSettings, UnknownCorpusVersionError
from meritum_core.shared.embeddings import build_embeddings
from meritum_core.shared.llm import LlmSettings, build_llm
from pydantic import ValidationError

from meritum_worker.observability.cases import load_eval_cases
from meritum_worker.observability.cassette import Cassette, EvalMode
from meritum_worker.observability.citation_judge import judge_citations
from meritum_worker.observability.comparison import (
    ModelComparison,
    ModelConfig,
    compare_models,
    load_model_config,
)
from meritum_worker.observability.constants import (
    DEFAULT_CASES_FILE,
    DEFAULT_MAX_CONCURRENCY,
    EVAL_NAME,
)
from meritum_worker.observability.factory import (
    build_api_checks,
    build_eval_deps,
    build_replay_deps,
    build_snapshot_corpus,
)
from meritum_worker.observability.gates import GATES_COMMAND, gates_eval
from meritum_worker.observability.models import GoldenSet
from meritum_worker.observability.report import EvalReport
from meritum_worker.observability.retrieval import (
    EmbeddingsComparison,
    EmbeddingsConfig,
    compare_embeddings,
    load_embeddings_config,
    score_retrieval,
)
from meritum_worker.observability.runner import DepsFor, run_cases, run_eval
from meritum_worker.observability.scoring import score_runs
from meritum_worker.observability.snapshot import SnapshotCorpus, load_snapshot_file


def meritum_eval(argv: Sequence[str] | None = None) -> None:
    """Evaluate the model from ``MERITUM_LLM_*``, or compare config files.

    ``meritum-eval gates`` compares the gates before the LLM instead (ADR-35).
    ``--mode record`` also writes every provider answer to ``--cassette``;
    ``--mode replay`` answers from it alone, without keys or network, pinned
    to the snapshot it recorded. No CI step runs a real provider.

    Args:
        argv: Command-line arguments; ``sys.argv`` when None.

    Features:
        US-OBS-04, US-OBS-05, US-OBS-07, US-WDR-02, F-27, ADR-28
    """
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == GATES_COMMAND:
        gates_eval(argv[1:])
        return
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
    parser.add_argument("--mode", type=EvalMode, default=EvalMode.LIVE)
    parser.add_argument("--cassette", type=Path, help="needed by record and replay")
    parser.add_argument("--corpus-version", help="snapshot every check is pinned to")
    parser.add_argument(
        "--corpus-file", type=Path, help="saved snapshot --compare-embeddings searches"
    )
    parser.add_argument("--api", help="origin of a deployed API to check the cases on")
    parser.add_argument(
        "--judge", action="store_true", help="judge citations with MERITUM_LLM_*"
    )
    parser.add_argument(
        "--fresh", action="store_true", help="bypass the API's result cache"
    )
    args = parser.parse_args(argv)
    try:
        cases = load_eval_cases(args.cases)
    except (OSError, TypeError, ValueError, csv.Error) as error:
        # Too few cases, bad JSON or an invalid case: a message, not a traceback.
        parser.error(f"{args.cases}: {error}")
    try:
        # Every file loads before any model runs, so a typo costs nothing.
        models = [load_model_config(path) for path in args.compare_models]
        embeddings = [load_embeddings_config(p) for p in args.compare_embeddings]
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        parser.error(f"config: {error}")
    recorded: Cassette | None = None
    if (models or embeddings) and args.mode is not EvalMode.LIVE:
        parser.error("a comparison runs live; record or replay one model")
    if embeddings:
        corpus = _snapshot(parser, args)
        report = asyncio.run(_compare_embeddings(cases, args.cases, embeddings, corpus))
    elif models:
        report = asyncio.run(
            _compare_models(cases, args.cases, models, args.max_concurrency)
        )
    elif args.api:
        report = asyncio.run(_through_api(cases, args, args.max_concurrency))
    else:
        deps_for, recorded = _deps(parser, args)
        report = score_runs(
            asyncio.run(run_eval(cases, deps_for, args.max_concurrency))
        )
    text = report.model_dump_json(indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.write_text(text, encoding="utf-8")
    if recorded is not None:
        recorded.save(args.cassette)


async def _compare_models(
    cases: GoldenSet,
    cases_file: Path,
    models: Sequence[ModelConfig],
    concurrency: int,
) -> ModelComparison:
    now = datetime.now(UTC)
    entries = [
        (c, await run_eval(cases, build_eval_deps(c.llm), concurrency)) for c in models
    ]
    return compare_models(entries, str(cases_file), now)


async def _compare_embeddings(
    cases: GoldenSet,
    cases_file: Path,
    embeddings: Sequence[EmbeddingsConfig],
    corpus: SnapshotCorpus,
) -> EmbeddingsComparison:
    now = datetime.now(UTC)
    scores = [
        await score_retrieval(cases, corpus, c, build_embeddings(c.embeddings))
        for c in embeddings
    ]
    return compare_embeddings(scores, str(cases_file), corpus.version, now)


def _snapshot(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> SnapshotCorpus:
    # A saved snapshot runs without the database; otherwise read the pinned one.
    if args.corpus_file is not None:
        try:
            corpus = load_snapshot_file(args.corpus_file)
        except (OSError, ValueError) as error:
            parser.error(f"{args.corpus_file}: {error}")
        if args.corpus_version not in {None, corpus.version}:
            parser.error(f"{args.corpus_file} holds snapshot {corpus.version}")
        return corpus
    if args.corpus_version is None:
        parser.error("--compare-embeddings needs --corpus-version or --corpus-file")
    reader = build_snapshot_corpus(CorpusSettings())
    if reader is None:
        parser.error("--corpus-version needs MERITUM_CORPUS_DATABASE_URL")
    try:
        return asyncio.run(reader.read(args.corpus_version))
    except UnknownCorpusVersionError as error:
        parser.error(str(error))


async def _through_api(
    cases: GoldenSet, args: argparse.Namespace, concurrency: int
) -> EvalReport:
    checks = build_api_checks(args.api, fresh=args.fresh)
    try:
        runs = await run_cases(cases, checks.check, concurrency)
    finally:
        await checks.aclose()
    report = score_runs(runs)
    if not args.judge:
        return report
    precision = await judge_citations(runs, build_llm(LlmSettings()))
    return report.model_copy(update={"citation_precision": precision})


def _deps(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[DepsFor, Cassette | None]:
    # The cassette is returned only when the run records into it.
    mode = EvalMode(args.mode)
    if mode is not EvalMode.LIVE and args.cassette is None:
        parser.error(f"--mode {mode} needs --cassette")
    if mode is EvalMode.REPLAY:
        return _replay_deps(parser, args), None
    if mode is EvalMode.RECORD and args.corpus_version is None:
        parser.error("--mode record needs --corpus-version: the bundle names it")
    recorder = Cassette() if mode is EvalMode.RECORD else None
    return build_eval_deps(LlmSettings(), args.corpus_version, recorder), recorder


def _replay_deps(parser: argparse.ArgumentParser, args: argparse.Namespace) -> DepsFor:
    if args.corpus_version is not None:
        parser.error("replay pins the snapshot recorded in the cassette")
    try:
        cassette = Cassette.load(args.cassette)
    except (OSError, ValueError) as error:
        parser.error(f"{args.cassette}: {error}")
    return build_replay_deps(cassette)


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        msg = f"must be at least 1, got {number}"
        raise argparse.ArgumentTypeError(msg)
    return number
