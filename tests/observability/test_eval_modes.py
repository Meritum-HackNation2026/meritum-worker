"""Evaluation modes: a pinned snapshot, recording and keyless replay (ADR-28)."""

import asyncio
import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from meritum_core.corpus import (
    CorpusSearchPort,
    CorpusSettings,
    Passage,
    build_corpus_search,
)
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.shared.embeddings import EmbeddingsPort
from meritum_core.shared.llm import LlmProvider, LlmSettings

from meritum_worker.checks import FakePageFetcher
from meritum_worker.checks import factory as checks_factory
from meritum_worker.observability import (
    Cassette,
    GoldenSet,
    Manifest,
    load_golden_set,
    meritum_eval_bundle,
    run_eval,
    score_runs,
)
from meritum_worker.observability.factory import build_eval_deps, build_replay_deps
from meritum_worker.observability.runner import DepsFor

ROOT = Path(__file__).resolve().parents[2]
STUB_ANSWER = ROOT / "features" / "fixtures" / "llm_stub_answer.json"
CASES = load_golden_set(ROOT / "evals" / "golden" / "cases.json")
TEXT_ONLY = CASES.model_copy(
    update={
        "root": tuple(c for c in CASES.root if c.text is not None and c.url is None)
    }
)
# The golden link cases carry text too; without it the check reads the page.
LINKS = GoldenSet.model_validate(
    [case.model_dump() | {"text": None} for case in CASES.root if case.url is not None]
)
PAGE = FetchedPage(
    url="https://www.gov.pl/web/rodzina/placa",
    content_type="text/html",
    untrusted_text="Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł brutto.",
)
STUB = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=STUB_ANSWER)
SNAPSHOT = "2026-11-20T10:00Z"
PASSAGE = Passage(
    passage_id="p-1",
    source_id="gov-placa",
    text="Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł brutto.",
    published_on=date(2025, 9, 15),
    fetched_at=datetime(2026, 11, 20, 9, tzinfo=UTC),
)


pytestmark = pytest.mark.usefixtures("snapshot")


@pytest.fixture
def snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """The memory corpus holds SNAPSHOT, as a recording's database would."""

    def with_snapshot(
        settings: CorpusSettings, embeddings: EmbeddingsPort
    ) -> CorpusSearchPort:
        return build_corpus_search(
            settings, embeddings, snapshots={SNAPSHOT: [PASSAGE]}
        )

    monkeypatch.setattr(checks_factory, "build_corpus_search", with_snapshot)


def _verdicts(deps_for: DepsFor, cases: GoldenSet = TEXT_ONLY) -> list[tuple[str, str]]:
    runs = asyncio.run(run_eval(cases, deps_for, 1))
    return [(run.case.id, run.result.status) for run in runs]


def test_pinned_snapshot_reaches_every_check() -> None:
    runs = asyncio.run(run_eval(TEXT_ONLY, build_eval_deps(STUB, SNAPSHOT), 1))
    # Cases without a fact skip the corpus and keep "none".
    assert {run.result.corpus_version for run in runs} == {SNAPSHOT, "none"}


def test_replay_repeats_the_recorded_run_without_a_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cassette = Cassette()
    recorded = _verdicts(build_eval_deps(STUB, SNAPSHOT, recorder=cassette))
    assert cassette.corpus_version == SNAPSHOT
    assert cassette.llm
    monkeypatch.setenv("MERITUM_LLM_PROVIDER", "vertex")
    replayed = asyncio.run(run_eval(TEXT_ONLY, build_replay_deps(cassette), 1))
    assert [(r.case.id, r.result.status) for r in replayed] == recorded
    assert score_runs(replayed).corpus_versions == (SNAPSHOT, "none")
    assert cassette.corpus


def test_replay_of_an_empty_cassette_never_reaches_a_provider() -> None:
    runs = asyncio.run(run_eval(TEXT_ONLY, build_replay_deps(Cassette()), 1))
    assert {run.result.status for run in runs} == {"technical_failure"}


def test_recorded_link_cases_fill_the_manifest_and_replay_alike(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recording = FakePageFetcher(PAGE)
    monkeypatch.setattr(checks_factory, "build_page_fetcher", lambda: recording)
    cassette = Cassette()
    recorded = _verdicts(build_eval_deps(STUB, SNAPSHOT, recorder=cassette), LINKS)
    assert recording.calls
    path = tmp_path / "cassettes" / "run.json"
    cassette.save(path)
    meritum_eval_bundle([
        "--cases", str(ROOT / "evals" / "golden" / "cases.json"),
        "--cassette", str(path), "--output", str(tmp_path / "bundle"),
    ])  # fmt: skip
    manifest = Manifest.model_validate_json(
        (tmp_path / "bundle" / "manifest.json").read_text(encoding="utf-8")
    )
    digest = hashlib.sha256(PAGE.untrusted_text.encode()).hexdigest()
    assert manifest.documents
    assert {document.sha256 for document in manifest.documents} == {digest}
    offline = FakePageFetcher()
    monkeypatch.setattr(checks_factory, "build_page_fetcher", lambda: offline)
    assert _verdicts(build_replay_deps(Cassette.load(path)), LINKS) == recorded
    assert offline.calls == []
