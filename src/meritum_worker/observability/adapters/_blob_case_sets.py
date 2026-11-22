"""EvalCaseSets over the golden file and staff datasets in BlobStore (core#124).

Features:
    US-OBS-06, US-POW-05, F-28, ADR-31
"""

import asyncio
from pathlib import Path

from meritum_core.checks.contracts import EvalCaseSet
from meritum_core.shared.blobs import BlobStore

from meritum_worker.observability.cases import parse_eval_cases
from meritum_worker.observability.golden import load_golden_set
from meritum_worker.observability.models import GoldenSet


class BlobCaseSets:
    """Reads the golden set from disk and user files from the blob store.

    Args:
        golden: the golden set's JSON file.
        blobs: where the backend stored uploaded case files.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-31
    """

    def __init__(self, golden: Path, blobs: BlobStore) -> None:
        self._golden = golden
        self._blobs = blobs

    async def load(
        self,
        case_set: EvalCaseSet,
        case_file: str | None,
        *,
        dataset_blob_id: str | None = None,
    ) -> GoldenSet:
        """Read the golden set or the blob the backend linked to the run.

        Args:
            case_set: the golden set or a user file.
            case_file: the upload's name; its suffix picks the parser.
            dataset_blob_id: the blob id from ``EvalRunInput``; only a user file
                run has one.

        Returns:
            The validated cases.

        Raises:
            LookupError: no blob is named, or the blob is missing.
        """
        if case_set == "golden":
            return await asyncio.to_thread(load_golden_set, self._golden)
        if dataset_blob_id is None:
            msg = "a user file run names the dataset blob"
            raise LookupError(msg)
        data = await self._blobs.get(dataset_blob_id)
        name = Path(case_file or "cases.json").name
        return await asyncio.to_thread(parse_eval_cases, data, name)
