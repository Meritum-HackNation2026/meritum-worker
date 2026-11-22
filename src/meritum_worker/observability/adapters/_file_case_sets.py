"""EvalCaseSets over files: the golden file and a directory of uploaded files.

shortcut: the backend writes the uploaded CSV into this directory (a shared
volume); read it from the store the backend picks once that is decided.

Features:
    US-OBS-06, US-POW-05, F-28
"""

import asyncio
from pathlib import Path

from meritum_core.checks.contracts import EvalCaseSet

from meritum_worker.observability.cases import load_eval_cases
from meritum_worker.observability.golden import load_golden_set
from meritum_worker.observability.models import GoldenSet


class FileCaseSets:
    """Reads the golden set and uploaded files from disk.

    Args:
        golden: the golden set's JSON file.
        uploads: the directory of uploaded case files.

    Features:
        US-OBS-06, US-POW-05, F-28
    """

    def __init__(self, golden: Path, uploads: Path) -> None:
        self._golden = golden
        self._uploads = uploads

    async def load(self, case_set: EvalCaseSet, case_file: str | None) -> GoldenSet:
        """Read the golden set or the named upload.

        Args:
            case_set: the golden set or a user file.
            case_file: the upload's name; only its last path part counts.

        Returns:
            The validated cases.

        Raises:
            LookupError: no upload has that name.
        """
        if case_set == "golden":
            return await asyncio.to_thread(load_golden_set, self._golden)
        # Path(...).name drops any directory part, so a name cannot leave uploads.
        path = self._uploads / Path(case_file or "").name
        if not path.is_file():
            msg = f"no case file {case_file!r}"
            raise LookupError(msg)
        return await asyncio.to_thread(load_eval_cases, path)
