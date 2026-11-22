"""In-memory run repository and case sets, for tests and local runs.

Features:
    US-OBS-06, F-28
"""

from collections.abc import Mapping

from meritum_core.checks.contracts import EvalCaseSet, EvalRun

from meritum_worker.observability.models import GoldenSet


class InMemoryEvalRuns:
    """EvalRunRepository that keeps the runs in a dict.

    Features:
        US-OBS-06, F-28
    """

    def __init__(self) -> None:
        self._runs: dict[str, EvalRun] = {}

    async def save(self, run: EvalRun) -> None:
        """Store ``run``, replacing one with the same id.

        Args:
            run: the run in its current state.
        """
        self._runs[run.id] = run

    async def get(self, run_id: str) -> EvalRun | None:
        """Read one run.

        Args:
            run_id: the run's id.

        Returns:
            The run, or None.
        """
        return self._runs.get(run_id)


class InMemoryCaseSets:
    """EvalCaseSets over a golden set and named files held in memory.

    Args:
        golden: the golden set.
        files: uploaded case files by name.

    Features:
        US-OBS-06, US-POW-05, F-28
    """

    def __init__(
        self, golden: GoldenSet, files: Mapping[str, GoldenSet] | None = None
    ) -> None:
        self._golden = golden
        self._files: dict[str, GoldenSet] = dict(files or {})

    async def load(self, case_set: EvalCaseSet, case_file: str | None) -> GoldenSet:
        """Give the golden set or the named file.

        Args:
            case_set: the golden set or a user file.
            case_file: the file's name; ignored for the golden set.

        Returns:
            The cases.

        Raises:
            LookupError: no file has that name.
        """
        if case_set == "golden":
            return self._golden
        cases = self._files.get(case_file or "")
        if cases is None:
            msg = f"no case file {case_file!r}"
            raise LookupError(msg)
        return cases
