"""The `check` workflow on real DBOS and PostgreSQL; local only (-m integration).

Needs PostgreSQL at MERITUM_DBOS_URL, e.g. `docker compose up -d --wait db` in the
backend repo; the restart test also needs MERITUM_TEST_DATABASE_URL (a database
where it may create and drop the schema app_integration).
"""

import asyncio
import os
from collections.abc import Callable, Iterator
from pathlib import Path

import psycopg
import pytest
from dbos import DBOS
from meritum_core.checks import AnalysisStatus, CheckRecordRepository
from meritum_core.jobs.constants import PROGRESS_KEY
from meritum_core.jobs.contracts import CHECK, CheckInput, CheckOutput
from meritum_core.shared.database.adapters import apply_migrations

from meritum_worker import main

APP_SCHEMA = "app_integration"
FIXTURE = Path(__file__).resolve().parents[2] / "features/fixtures/llm_stub_answer.json"


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> Iterator[CheckRecordRepository]:
    """Launch DBOS; yield the records the workflow saves."""
    monkeypatch.setenv("MERITUM_LLM_PROVIDER", "stub")
    monkeypatch.setenv("MERITUM_LLM_STUB_FIXTURES", str(FIXTURE))
    monkeypatch.setenv("MERITUM_DBOS_SCHEMA", "worker_integration")
    main.check_deps.cache_clear()
    DBOS(config=main.config())
    DBOS.launch()
    yield main.check_deps().records
    DBOS.destroy()
    main.check_deps.cache_clear()


async def _check(
    payload: dict[str, object], records: CheckRecordRepository
) -> tuple[CheckOutput, list[AnalysisStatus]]:
    handle = await DBOS.start_workflow_async(main.check_workflow, payload)
    output = CHECK.output.model_validate(await handle.get_result())
    stream = DBOS.read_stream_async(handle.workflow_id, PROGRESS_KEY)
    statuses = [AnalysisStatus.model_validate(value) async for value in stream]
    record = await records.get(handle.workflow_id)
    assert record is not None
    assert record.status == output.result.status == "done"
    return output, statuses


@pytest.mark.integration
def test_check_workflow_runs_on_dbos_and_streams_progress(
    records: CheckRecordRepository, make_job: Callable[..., CheckInput]
) -> None:
    payload = make_job().model_dump(mode="json")
    output, statuses = asyncio.run(_check(payload, records))
    assert statuses[-1].result == output.result
    assert {step.status for step in statuses[-1].steps} == {"done"}


@pytest.fixture
def app_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point MERITUM_DATABASE_* at a fresh, migrated app schema; drop it after."""
    base = os.environ["MERITUM_TEST_DATABASE_URL"]
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {APP_SCHEMA} CASCADE")
        conn.execute(f"CREATE SCHEMA {APP_SCHEMA}")
    url = f"{base}?options=-csearch_path%3D{APP_SCHEMA}"
    apply_migrations(url)
    monkeypatch.setenv("MERITUM_DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("MERITUM_DATABASE_URL", url)
    yield
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA {APP_SCHEMA} CASCADE")


def _restart() -> None:
    DBOS.destroy()
    main.check_deps.cache_clear()
    DBOS(config=main.config())
    DBOS.launch()


@pytest.mark.integration
@pytest.mark.usefixtures("app_database")
def test_check_record_survives_worker_restart(
    records: CheckRecordRepository, make_job: Callable[..., CheckInput]
) -> None:
    payload = make_job().model_dump(mode="json")
    output, _ = asyncio.run(_check(payload, records))
    check_id = output.result.check_id
    _restart()
    saved = asyncio.run(main.check_deps().records.get(check_id))
    assert saved is not None
    assert saved.status == "done"
    handle = DBOS.retrieve_workflow(check_id)
    assert CHECK.output.model_validate(handle.get_result()) == output
