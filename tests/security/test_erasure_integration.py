"""delete_subject and retention on DBOS and PostgreSQL; local only (-m integration).

Needs PostgreSQL at MERITUM_DBOS_URL and MERITUM_TEST_DATABASE_URL (a database where
the test may create and drop the schemas app_erasure and worker_erasure), e.g.
`docker compose up -d --wait db` in the backend repo.
"""

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from dbos import DBOS
from meritum_core.checks import CheckRequest
from meritum_core.checks.contracts import CheckRecord
from meritum_core.jobs.contracts import CheckInput
from meritum_core.observability import build_app_repositories
from meritum_core.shared.database import DatabaseSettings
from meritum_core.shared.database.adapters import apply_migrations
from psycopg import sql

from meritum_worker import main, security

URL = os.environ.get("MERITUM_TEST_DATABASE_URL", "")
APP_SCHEMA, DBOS_SCHEMA = "app_erasure", "worker_erasure"
SESSION, OTHER = "s_12345678", "s_87654321"
FIXTURE = Path(__file__).resolve().parents[2] / "features/fixtures/llm_stub_answer.json"


def _reset(*schemas: str) -> None:
    with psycopg.connect(URL, autocommit=True) as conn:
        for schema in schemas:
            name = sql.Identifier(schema)
            conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(name))


@pytest.fixture
def app_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Migrate a fresh app schema, launch DBOS in a fresh schema; yield the app URL."""
    _reset(APP_SCHEMA, DBOS_SCHEMA)
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(APP_SCHEMA)))
    joiner = "&" if "?" in URL else "?"
    url = f"{URL}{joiner}options=-csearch_path%3D{APP_SCHEMA}"
    apply_migrations(url)
    for name, value in {
        "MERITUM_DATABASE_PROVIDER": "postgres",
        "MERITUM_DATABASE_URL": url,
        "MERITUM_DBOS_URL": URL,
        "MERITUM_DBOS_SCHEMA": DBOS_SCHEMA,
        "MERITUM_LLM_PROVIDER": "stub",
        "MERITUM_LLM_STUB_FIXTURES": str(FIXTURE),
    }.items():
        monkeypatch.setenv(name, value)
    main.check_deps.cache_clear()
    DBOS(config=main.config())
    DBOS.launch()
    yield url
    DBOS.destroy()
    main.check_deps.cache_clear()
    _reset(APP_SCHEMA, DBOS_SCHEMA)


async def _check(session: str) -> str:
    job = CheckInput(
        request=CheckRequest(channel="web", text="Płaca minimalna wynosi 4806 zł"),
        received_at=datetime.now(UTC),
        session_id=session,
    )
    handle = await DBOS.start_workflow_async(
        main.check_workflow, job.model_dump(mode="json")
    )
    await handle.get_result()
    return handle.workflow_id


def _late_record() -> CheckRecord:
    now = datetime.now(UTC)
    return CheckRecord(
        check_id="chk_late",
        session_id=SESSION,
        channel="web",
        received_at=now,
        answered_at=now,
        question_masked="Płaca minimalna wynosi 4806 zł",
        status="done",
        verdicts=["confirmed"],
        source_ids=[],
        corpus_version="c1",
        models=[],
        retention_until=now + timedelta(days=30),
    )


async def _erase() -> str:
    payload = {"kind": "session_id", "value": SESSION}
    handle = await DBOS.start_workflow_async(main.delete_subject_workflow, payload)
    # A cancelled check's save step lands its record after the first pass.
    while not await DBOS.list_workflow_steps_async(handle.workflow_id):  # ruff: ignore[async-busy-wait]  # DBOS has no event for a finished step
        await asyncio.sleep(0.05)
    records = build_app_repositories(DatabaseSettings()).records
    await records.save(_late_record())
    assert (await handle.get_result())["deleted"] > 0
    return handle.workflow_id


async def _retain() -> None:
    # The erasure run keeps its input for an hour; the next retention run drops it.
    deps = security.build_retention_deps(DatabaseSettings(), None)
    await security.run_retention(deps, datetime.now(UTC) + timedelta(hours=2))


def _rows_naming(value: str, skip: str = "", unless: str | None = None) -> int:
    """Count rows of all tables but ``skip`` naming ``value`` and not ``unless``."""
    found = 0
    with psycopg.connect(URL) as conn:
        tables = conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables"
            " WHERE table_schema = ANY(%s) AND table_type = 'BASE TABLE'"
            " AND table_name <> %s",
            ([APP_SCHEMA, DBOS_SCHEMA], skip),
        ).fetchall()
        for schema, table in tables:
            name = sql.Identifier(schema, table)
            query = sql.SQL(
                "SELECT count(*) FROM {} t"
                " WHERE t::text LIKE %s AND t::text NOT LIKE %s"
            )
            # NOT LIKE NULL is never true, so no ``unless`` must not filter.
            patterns = (f"%{value}%", "" if unless is None else f"%{unless}%")
            row = conn.execute(query.format(name), patterns).fetchone()
            found += 0 if row is None else int(row[0])
    return found


@pytest.mark.integration
@pytest.mark.skipif(not URL, reason="set MERITUM_TEST_DATABASE_URL")
def test_no_row_names_the_session_after_erasure(
    app_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert app_url
    monkeypatch.setattr(security, "ERASURE_SETTLE", timedelta(seconds=3))
    erased = asyncio.run(_check(SESSION))
    kept = asyncio.run(_check(OTHER))
    assert _rows_naming(SESSION) > 0
    run = asyncio.run(_erase())
    # Right after the erasure only the erasure run itself names the session.
    assert _rows_naming(SESSION, unless=run) == 0
    assert _rows_naming(SESSION) > 0
    asyncio.run(_retain())
    assert _rows_naming(SESSION) == 0
    # Only the bare id stays, so a stale case save cannot bring it back (core#74).
    assert _rows_naming(erased, skip="removed_case_checks") == 0
    assert _rows_naming(OTHER) > 0
    assert _rows_naming(kept) > 0
