"""Corpus workflows and schedules on real DBOS and PostgreSQL; local only.

Needs PostgreSQL at MERITUM_DBOS_URL (like tests/checks/test_check_dbos.py) and
runs with ``-m integration``. The corpus writer stays in memory and no catalogue
entry is due, so nothing is fetched and nothing reaches ``corpus``.
"""

import asyncio
from collections.abc import Callable, Coroutine, Iterator
from datetime import UTC, datetime

import pytest
from dbos import DBOS

from meritum_worker import main

SCHEDULED = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


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
def test_ingest_workflow_plans_before_it_fetches(
    dbos: type[DBOS], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MERITUM_CORPUS_INGEST", "")
    steps = asyncio.run(_steps(dbos, main.corpus_ingest_workflow))
    assert steps == [("plan due entries", "[]")]
