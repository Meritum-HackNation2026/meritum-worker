"""Ports of an evaluation run: where the run is stored and where its cases come from.

Features:
    US-OBS-06, F-28, ADR-28
"""

from typing import Protocol

from meritum_core.checks.contracts import EvalCaseSet, EvalRun

from meritum_worker.observability.models import GoldenSet


class EvalRunRepository(Protocol):
    """Stores evaluation runs; the worker writes them and the backend reads them.

    Features:
        US-OBS-06, F-28, ADR-28
    """

    async def save(self, run: EvalRun) -> None:
        """Store ``run``, replacing a stored one with the same id.

        Args:
            run: the run in its current state.
        """
        ...

    async def get(self, run_id: str) -> EvalRun | None:
        """Read one run.

        Args:
            run_id: the run's id.

        Returns:
            The run, or None when no run has that id.
        """
        ...


class EvalCaseSets(Protocol):
    """Gives the cases of the golden set or of a file a staff user uploaded.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-28
    """

    async def load(self, case_set: EvalCaseSet, case_file: str | None) -> GoldenSet:
        """Read and validate the cases of a run.

        Args:
            case_set: the golden set or a user file.
            case_file: the uploaded file's name; None for the golden set.

        Returns:
            The validated cases.

        Raises:
            LookupError: no file has that name.
            ValueError: the file is not a valid case file.
        """
        ...
