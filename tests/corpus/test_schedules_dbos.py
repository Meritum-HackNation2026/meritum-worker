"""Corpus workflows and schedules on real DBOS and PostgreSQL; local only.

Needs PostgreSQL at MERITUM_DBOS_URL (like tests/checks/test_check_dbos.py) and
runs with ``-m integration``. The catalogue, fetcher and writer are fakes, so
nothing is fetched from the network and nothing reaches ``corpus``.
"""

import asyncio
from collections.abc import Callable, Coroutine, Iterator
from datetime import UTC, datetime

import pytest
from dbos import DBOS
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus, main
from meritum_worker.corpus.fakes import FakeCatalogSite
from meritum_worker.security import CleanInjectionDetector

SCHEDULED = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
ENTRY = CatalogEntry(
    domain="urzad.gov.pl",
    publisher="Urząd",
    publisher_id="urzad",
    kind="instytucja",
    tier="primary",
    license="CC BY 4.0",
    ingest="static",
    qualified_because="Źródło z listy organizatora konkursu.",
)


@pytest.fixture
def dbos(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[DBOS]]:
    monkeypatch.setenv("MERITUM_DBOS_SCHEMA", "worker_corpus_integration")
    monkeypatch.setenv("MERITUM_CORPUS_PROVIDER", "memory")
    monkeypatch.setenv("MERITUM_CORPUS_INGEST", "enabled")
    DBOS(config=main.config())
    DBOS.launch()
    yield DBOS
    DBOS.destroy()


type Workflow = Callable[[datetime, object], Coroutine[object, object, None]]


async def _steps(dbos: type[DBOS], workflow: Workflow) -> list[tuple[str, str]]:
    handle = await dbos.start_workflow_async(workflow, SCHEDULED, None)
    await handle.get_result()
    steps = await dbos.list_workflow_steps_async(handle.workflow_id)
    return [(step["function_name"], str(step["output"])) for step in steps]


@pytest.mark.integration
def test_snapshot_workflow_takes_the_version_of_its_hour(dbos: type[DBOS]) -> None:
    steps = asyncio.run(_steps(dbos, main.corpus_snapshot_workflow))
    assert steps == [("take snapshot", "2026-11-20T10:00Z (0 documents)")]


@pytest.mark.integration
def test_ingest_workflow_stores_the_pages_of_each_due_entry(
    dbos: type[DBOS], monkeypatch: pytest.MonkeyPatch
) -> None:
    site = FakeCatalogSite(pages_per_domain=3)
    deps = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=corpus.build_corpus_writer(),
        injection=CleanInjectionDetector(),
    )
    catalog = (
        ENTRY,
        ENTRY.model_copy(update={"domain": "live.gov.pl", "ingest": "live"}),
    )
    monkeypatch.setattr(main, "_ingest_deps", lambda: deps)
    monkeypatch.setattr(main, "load_catalog", lambda: catalog)
    steps = asyncio.run(_steps(dbos, main.corpus_ingest_workflow))
    assert [name for name, _ in steps] == ["plan due entries", "ingest urzad.gov.pl"]
    assert corpus.IngestReport.model_validate_json(steps[1][1]).added == 3
    documents = asyncio.run(deps.store.documents())
    assert {d.fetched_at for d in documents} == {SCHEDULED}


@pytest.mark.integration
def test_ingest_workflow_plans_nothing_when_not_enabled(
    dbos: type[DBOS], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MERITUM_CORPUS_INGEST", "")
    steps = asyncio.run(_steps(dbos, main.corpus_ingest_workflow))
    assert steps == [("plan due entries", "[]")]
