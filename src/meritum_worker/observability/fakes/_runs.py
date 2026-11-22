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
    """EvalCaseSets over a golden set and datasets held in memory by blob id.

    Args:
        golden: the golden set.
        datasets: uploaded case sets by blob id.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-31
    """

    def __init__(
        self, golden: GoldenSet, datasets: Mapping[str, GoldenSet] | None = None
    ) -> None:
        self._golden = golden
        self._datasets: dict[str, GoldenSet] = dict(datasets or {})

    async def load(
        self,
        case_set: EvalCaseSet,
        case_file: str | None,
        *,
        dataset_blob_id: str | None = None,
    ) -> GoldenSet:
        """Give the golden set or the dataset named by blob id.

        Args:
            case_set: the golden set or a user file.
            case_file: the file's name; ignored except in error messages.
            dataset_blob_id: the blob id from ``EvalRunInput``.

        Returns:
            The cases.

        Raises:
            LookupError: no dataset is named.
        """
        if case_set == "golden":
            return self._golden
        if dataset_blob_id is None:
            msg = "a user file run names the dataset blob"
            raise LookupError(msg)
        cases = self._datasets.get(dataset_blob_id)
        if cases is None:
            msg = f"no case file {case_file!r}"
            raise LookupError(msg)
        return cases
