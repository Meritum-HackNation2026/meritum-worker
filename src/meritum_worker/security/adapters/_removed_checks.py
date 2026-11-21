"""RemovedCaseChecks over the ``removed_case_checks`` table of the app schema (core#74).

Features:
    US-BEZ-05, F-20, ADR-13
"""

from datetime import datetime

from psycopg import AsyncConnection


class PostgresRemovedCaseChecks:
    """Deletes old rows of ``removed_case_checks``.

    Args:
        conninfo: libpq connection string; its ``search_path`` names the app schema.

    Features:
        US-BEZ-05, F-20, ADR-13
    """

    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    async def purge(self, before: datetime) -> int:
        """Forget checks removed before ``before``.

        Args:
            before: older rows go.

        Returns:
            How many rows were deleted.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = await conn.execute(
                "DELETE FROM removed_case_checks WHERE removed_at < %s", (before,)
            )
            return cursor.rowcount


class NullRemovedCaseChecks:
    """RemovedCaseChecks for the in-memory app repositories, which keep no such table.

    Features:
        US-BEZ-05, F-20
    """

    async def purge(self, before: datetime) -> int:  # ruff: ignore[no-self-use]  # RemovedCaseChecks is an instance protocol
        """Delete nothing.

        Args:
            before: ignored.

        Returns:
            0.
        """
        del before
        return 0
