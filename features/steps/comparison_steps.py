"""Steps for the model comparison scenarios of observability.feature (#40)."""

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.corpus import Passage

from meritum_worker.observability import (
    SnapshotCorpus,
    load_golden_set,
    meritum_eval,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "evals" / "golden" / "cases.json"
STUB_ANSWER = ROOT / "features" / "fixtures" / "llm_stub_answer.json"
VERSION = "2026-11-22T04:00Z"
TAKEN_AT = datetime(2026, 11, 22, 4, tzinfo=UTC)
HYBRID_TOP_K = 20
COMPARED_METRICS = (
    "macro_f1",
    "citation_correctness",
    "median_seconds",
    "output_tokens_per_second",
    "cost_100_checks_usd",
)


def _folder(context: Context) -> Path:
    folder = Path(tempfile.mkdtemp())
    context.add_cleanup(shutil.rmtree, folder)
    context.report_path = folder / "comparison.json"
    return folder


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


@given("golden set i dwie konfiguracje modelu głównego")
def two_model_configs(context: Context) -> None:
    folder = _folder(context)
    context.configs = [
        _write(
            folder / f"config-{name}.toml",
            f'name = "{name}"\n[llm]\nprovider = "stub"\n'
            f'reasoning = "{reasoning}"\nstub_fixtures = "{STUB_ANSWER}"\n',
        )
        for name, reasoning in (("a", "high"), ("b", "low"))
    ]


@when(
    'zespół uruchamia "uv run meritum-eval --compare-models config-a.toml'
    ' config-b.toml"'
)
def team_compares_models(context: Context) -> None:
    meritum_eval(
        [
            "--compare-models",
            *context.configs,
            "--cases",
            str(GOLDEN),
            "--output",
            str(context.report_path),
        ]
    )


@then(
    "raport podaje dla każdej konfiguracji macro-F1, poprawność cytowań, medianę"
    " czasu, tokeny na sekundę i koszt 100 testów"
)
def report_compares_models(context: Context) -> None:
    report = json.loads(context.report_path.read_text(encoding="utf-8"))
    assert report["generated_at"]
    assert [m["name"] for m in report["models"]] == ["a", "b"]
    for model in report["models"]:
        assert model["model"]
        assert model["region"]
        for metric in COMPARED_METRICS:
            assert metric in model["report"], metric


def _snapshot(folder: Path) -> str:
    # The golden set's sources as corpus documents, plus one nobody cites.
    cases = load_golden_set(GOLDEN)
    sources = {str(s.url): s for case in cases.root for s in case.sources}
    urls = {f"doc-{i}": url for i, url in enumerate(sources)}
    texts = {i: f"{sources[u].title}\n{sources[u].quote}" for i, u in urls.items()}
    urls["doc-other"] = "https://example.pl/inny"
    texts["doc-other"] = "Rozkład jazdy autobusów w Pcimiu."
    passages = tuple(
        Passage(
            passage_id=f"{doc}-0",
            source_id=doc,
            text=text,
            published_on=None,
            fetched_at=TAKEN_AT,
        )
        for doc, text in texts.items()
    )
    corpus = SnapshotCorpus(
        version=VERSION, taken_at=TAKEN_AT, urls=urls, passages=passages
    )
    return _write(folder / "snapshot.json", corpus.model_dump_json())


@given("korpus wczytany z migawki i dwie konfiguracje modelu embeddingów")
def two_embeddings_configs(context: Context) -> None:
    folder = _folder(context)
    context.corpus_file = _snapshot(folder)
    context.configs = [
        _write(
            folder / f"embeddings-{name}.toml",
            f'name = "{name}"\nusd_per_million_chars = 0.1\n'
            f'[embeddings]\nprovider = "stub"\ndimensions = {dimensions}\n',
        )
        for name, dimensions in (("a", 768), ("b", 64))
    ]


@when("zespół uruchamia porównanie")
def team_compares_embeddings(context: Context) -> None:
    meritum_eval(
        [
            "--compare-embeddings",
            *context.configs,
            "--corpus-file",
            context.corpus_file,
            "--cases",
            str(GOLDEN),
            "--output",
            str(context.report_path),
        ]
    )


@then(
    "raport podaje trafność wyszukiwania w korpusie na przypadkach z golden setu,"
    " z top 20 jak w wyszukiwaniu hybrydowym, i koszt"
)
def report_compares_embeddings(context: Context) -> None:
    report = json.loads(context.report_path.read_text(encoding="utf-8"))
    assert [m["name"] for m in report["models"]] == ["a", "b"]
    for model in report["models"]:
        assert model["top_k"] == HYBRID_TOP_K
        assert model["queries_with_targets"] > 0
        assert 0 <= model["hit_rate"] <= 1
        assert 0 < model["mean_reciprocal_rank"] <= 1
        assert model["cost_usd"] > 0


@then(
    "pole corpus w raporcie wskazuje migawkę corpus_version zamiast korpusu zastępczego"
)
def report_names_the_snapshot(context: Context) -> None:
    report = json.loads(context.report_path.read_text(encoding="utf-8"))
    assert report["corpus"] == VERSION
