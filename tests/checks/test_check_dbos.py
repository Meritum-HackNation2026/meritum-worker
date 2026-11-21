"""The `check` workflow on real DBOS and PostgreSQL; local only (-m integration).

Needs PostgreSQL at MERITUM_DBOS_URL, e.g. `docker compose up -d --wait db` in the
backend repo.
"""

import asyncio
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from dbos import DBOS
from meritum_core.checks import AnalysisStatus, CheckRecordRepository
from meritum_core.jobs.constants import PROGRESS_KEY
from meritum_core.jobs.contracts import CHECK, CheckInput, CheckOutput

from meritum_worker import main

FIXTURE = Path(__file__).resolve().parents[2] / "features/fixtures/llm_stub_answer.json"


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> Iterator[CheckRecordRepository]:
    """Launch DBOS on a clean schema; yield the records the workflow saves."""
    monkeypatch.setenv("MERITUM_LLM_PROVIDER", "stub")
    monkeypatch.setenv("MERITUM_LLM_STUB_FIXTURES", str(FIXTURE))
    monkeypatch.setenv("MERITUM_DBOS_SCHEMA", "worker_integration")
    main.check_deps.cache_clear()
    DBOS(config=main.config())
    DBOS.reset_system_database()
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
