"""Steps for the replay and bundle scenarios of features/observability.feature."""

import json
import os
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from behave import given, then, when
from behave.runner import Context
from meritum_core.corpus import (
    CorpusSearchPort,
    CorpusSettings,
    Passage,
    build_corpus_search,
)
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.shared.embeddings import EmbeddingsPort

from meritum_worker.checks import factory as checks_factory
from meritum_worker.observability import (
    Cassette,
    PageTake,
    load_golden_set,
    meritum_eval,
    meritum_eval_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "evals" / "golden" / "cases.json"
STUB_ANSWER = ROOT / "features" / "fixtures" / "llm_stub_answer.json"
SNAPSHOT = "2026-11-20T10:00Z"
CASES = 30
PAGE_TEXT = "Pełny tekst strony źródłowej, który nie może trafić do paczki. " * 20
# Timing differs between runs; everything else in the report must match.
TIMING = {"median_seconds", "p95_seconds", "max_seconds"}


def _folder(context: Context) -> Path:
    folder = Path(tempfile.mkdtemp())
    context.add_cleanup(shutil.rmtree, folder)
    return folder


def _text_cases() -> list[dict[str, object]]:
    # Text-only cases need no page fetch, so recording reaches no network.
    plain = [
        case.model_dump(mode="json")
        for case in load_golden_set(GOLDEN).root
        if case.text is not None
        and case.url is None
        and case.related_case is None
        and case.injection is None
    ]
    return [
        plain[i % len(plain)] | {"id": f"{plain[i % len(plain)]['id']}-{i}"}
        for i in range(CASES)
    ]


def _set(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


@contextmanager
def _env(**values: str | None) -> Generator[None]:
    previous = {name: os.environ.get(name) for name in values}
    for name, value in values.items():
        _set(name, value)
    try:
        yield
    finally:
        for name, value in previous.items():
            _set(name, value)


def _with_snapshot(
    settings: CorpusSettings, embeddings: EmbeddingsPort
) -> CorpusSearchPort:
    passage = Passage(
        passage_id="p-1",
        source_id="gov-placa",
        text="Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł brutto.",
        published_on=date(2025, 9, 15),
        fetched_at=datetime(2026, 11, 20, 9, tzinfo=UTC),
    )
    return build_corpus_search(settings, embeddings, snapshots={SNAPSHOT: [passage]})


def _report(path: Path) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    for case in report["outcomes"]:
        case.pop("seconds")
    return {k: v for k, v in report.items() if k not in TIMING}


@given("nagrane kasety i migawka 2026-11-20T10:00Z")
def recorded_cassette(context: Context) -> None:
    folder = _folder(context)
    context.cases = folder / "cases.json"
    context.cases.write_text(json.dumps(_text_cases()), encoding="utf-8")
    context.cassette = folder / "cassette.json"
    context.recorded = folder / "recorded.json"
    context.replayed = folder / "replayed.json"
    # The recording's corpus holds the snapshot; replay gets an empty one.
    unpinned = checks_factory.build_corpus_search
    setattr(checks_factory, "build_corpus_search", _with_snapshot)  # ruff: ignore[set-attr-with-constant]
    context.add_cleanup(setattr, checks_factory, "build_corpus_search", unpinned)
    with _env(MERITUM_LLM_PROVIDER="stub", MERITUM_LLM_STUB_FIXTURES=str(STUB_ANSWER)):
        meritum_eval([
            "--cases", str(context.cases), "--output", str(context.recorded),
            "--mode", "record", "--cassette", str(context.cassette),
            "--corpus-version", SNAPSHOT,
        ])  # fmt: skip
    setattr(checks_factory, "build_corpus_search", unpinned)  # ruff: ignore[set-attr-with-constant]


@when("ktoś uruchamia ewaluację w trybie replay bez kluczy dostawców")
def replay_without_keys(context: Context) -> None:
    # A real provider with no credentials: replay must never build it.
    with _env(MERITUM_LLM_PROVIDER="vertex", MERITUM_LLM_STUB_FIXTURES=None):
        meritum_eval([
            "--cases", str(context.cases), "--output", str(context.replayed),
            "--mode", "replay", "--cassette", str(context.cassette),
        ])  # fmt: skip


@then("wyniki są identyczne z przebiegiem nagrania")
def same_results(context: Context) -> None:
    recorded = _report(context.recorded)
    assert SNAPSHOT in cast("list[str]", recorded["corpus_versions"])
    outcomes = cast("list[dict[str, object]]", recorded["outcomes"])
    assert any(case["outcome"] == "correct" for case in outcomes)
    assert _report(context.replayed) == recorded


@when("zespół tworzy paczkę do odtworzenia")
def team_builds_bundle(context: Context) -> None:
    folder = _folder(context)
    page = FetchedPage(
        url="https://www.gov.pl/web/rodzina/placa",
        content_type="text/html",
        untrusted_text=PAGE_TEXT,
    )
    cassette = Cassette(corpus_version=SNAPSHOT)
    cassette.pages["key-1"] = [
        PageTake(page=page, fetched_at=datetime(2026, 11, 20, 9, tzinfo=UTC))
    ]
    context.cassette = folder / "cassette.json"
    cassette.save(context.cassette)
    context.bundle = folder / "bundle"
    meritum_eval_bundle([
        "--cases", str(GOLDEN), "--cassette", str(context.cassette),
        "--output", str(context.bundle),
    ])  # fmt: skip


@then(
    "paczka zawiera przypadki, adresy źródeł, cytowane fragmenty i manifest"
    " z identyfikatorami dokumentów, sumami kontrolnymi i fetched_at"
)
def bundle_has_everything(context: Context) -> None:
    cases = json.loads((context.bundle / "cases.json").read_text(encoding="utf-8"))
    assert len(cases) == len(load_golden_set(GOLDEN).root)
    sources = json.loads((context.bundle / "sources.json").read_text(encoding="utf-8"))
    assert sources
    assert all(source["url"] and source["quote"] for source in sources)
    manifest = json.loads(
        (context.bundle / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["corpus_version"] == SNAPSHOT
    [document] = manifest["documents"]
    assert document["document_id"] == "key-1"
    assert len(document["sha256"]) == 64  # ruff: ignore[magic-value-comparison]  # hex SHA-256
    assert document["fetched_at"].startswith("2026-11-20T09:00")


@then("nie zawiera pełnych tekstów ani kaset")
def bundle_has_no_texts(context: Context) -> None:
    files = sorted(p for p in context.bundle.rglob("*") if p.is_file())
    assert [p.name for p in files] == ["cases.json", "manifest.json", "sources.json"]
    for path in files:
        content = path.read_text(encoding="utf-8")
        assert PAGE_TEXT.strip()[:60] not in content, path.name
        assert "untrusted_text" not in content, path.name
