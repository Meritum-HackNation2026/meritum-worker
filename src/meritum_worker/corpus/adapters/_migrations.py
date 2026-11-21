"""Applies meritum-core's corpus SQL migrations once each, in file-name order.

shortcut: core ships a runner for the app schema only (meritum-migrate-app); move
this one next to it when core gets a corpus runner.

Features:
    US-KOR-02, F-12, ADR-04, ADR-32
"""

from importlib.resources import files

import psycopg

from meritum_worker.corpus.constants import (
    MIGRATION_SUFFIX,
    MIGRATIONS_DIRECTORY,
    MIGRATIONS_LOCK,
    MIGRATIONS_PACKAGE,
)


def apply_corpus_migrations(conninfo: str) -> list[str]:
    """Apply the corpus migrations not yet recorded in ``corpus.schema_migrations``.

    Everything runs in one transaction under an advisory lock, so a failed file
    leaves the schema as it was. ``corpus`` is not on the role's ``search_path``
    (infra#13), so the version table is named with its schema.

    Args:
        conninfo: libpq connection string of a role that owns ``corpus``.

    Returns:
        The file names applied by this run; empty when the schema is up to date.

    Raises:
        RuntimeError: a migration failed; the message starts with its file name.

    Features:
        US-KOR-02, F-12, ADR-32
    """
    directory = files(MIGRATIONS_PACKAGE) / MIGRATIONS_DIRECTORY
    scripts = sorted(
        (f for f in directory.iterdir() if f.name.endswith(MIGRATION_SUFFIX)),
        key=lambda f: f.name,
    )
    with psycopg.connect(conninfo) as conn, conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATIONS_LOCK,))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS corpus.schema_migrations ("
            " name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        rows = conn.execute("SELECT name FROM corpus.schema_migrations").fetchall()
        done = {name for (name,) in rows}
        applied = [s for s in scripts if s.name not in done]
        for script in applied:
            try:
                conn.execute(script.read_bytes())
            except psycopg.Error as exc:
                msg = f"{script.name}: {exc}"
                raise RuntimeError(msg) from exc
            conn.execute(
                "INSERT INTO corpus.schema_migrations (name) VALUES (%s)",
                (script.name,),
            )
    return [s.name for s in applied]
