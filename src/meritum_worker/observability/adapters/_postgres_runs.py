"""EvalRunRepository over one ``eval_runs`` table of the app schema.

shortcut: the table is created here on first use, as one JSONB document per run;
move it to a meritum-core app migration once the backend lists runs in SQL.

Features:
    US-OBS-06, F-28, ADR-04
"""

from meritum_core.checks.contracts import EvalRun
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from meritum_worker.observability.constants import (
    CREATE_EVAL_RUNS_SQL,
    UPSERT_EVAL_RUN_SQL,
)


class PostgresEvalRuns:
    """Stores each run as JSON next to its id, user and start.

    Args:
        conninfo: libpq connection string of the app database.

    Features:
        US-OBS-06, F-28, ADR-04
    """

    def __init__(self, conninfo: str) -> None:
        # shortcut: one connection per call; take a pool when runs are hot.
        self._conninfo = conninfo

    async def save(self, run: EvalRun) -> None:
        """Store ``run``, replacing one with the same id.

        Args:
            run: the run in its current state.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute(CREATE_EVAL_RUNS_SQL)
            await conn.execute(
                UPSERT_EVAL_RUN_SQL,
                (
                    run.id,
                    run.user_id,
                    run.started_at,
                    Jsonb(run.model_dump(mode="json")),
                ),
            )

    async def get(self, run_id: str) -> EvalRun | None:
        """Read one run.

        Args:
            run_id: the run's id.

        Returns:
            The run, or None.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute(CREATE_EVAL_RUNS_SQL)
            cursor = await conn.execute(
                "SELECT run FROM eval_runs WHERE id = %s", (run_id,)
            )
            row = await cursor.fetchone()
        return None if row is None else EvalRun.model_validate(row[0])
