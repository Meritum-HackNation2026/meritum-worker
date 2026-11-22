"""PostgresEvalRuns on a real database: local only, ``uv run pytest -m integration``.

Needs ``MERITUM_TEST_DATABASE_URL``; the test removes the run it wrote.
"""

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest
from meritum_core.checks.contracts import EvalRun

from meritum_worker.observability.adapters import PostgresEvalRuns

pytestmark = pytest.mark.integration
RUN_ID = "integration-run"


@pytest.fixture
def url() -> Iterator[str]:
    value = os.environ.get("MERITUM_TEST_DATABASE_URL", "")
    if not value:
        pytest.skip("set MERITUM_TEST_DATABASE_URL to a PostgreSQL database")
    yield value
    with psycopg.connect(value, autocommit=True) as conn:
        conn.execute("DELETE FROM eval_runs WHERE id = %s", (RUN_ID,))


def test_a_saved_run_is_read_back_and_a_second_save_replaces_it(url: str) -> None:
    runs = PostgresEvalRuns(url)
    started = datetime(2026, 11, 22, 12, tzinfo=UTC)
    running = EvalRun(
        id=RUN_ID,
        case_set="golden",
        status="running",
        corpus_version="v1",
        user_id="google:1234567890",
        started_at=started,
    )
    asyncio.run(runs.save(running))
    failed = running.model_copy(update={"status": "failed", "finished_at": started})
    asyncio.run(runs.save(failed))
    assert asyncio.run(runs.get(RUN_ID)) == failed
    assert asyncio.run(runs.get("absent")) is None
