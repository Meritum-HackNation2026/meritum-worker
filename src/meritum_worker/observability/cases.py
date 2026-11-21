"""Read an evaluation case file: JSON or CSV, at least MIN_EVAL_CASES cases.

Features:
    US-OBS-04, US-OBS-05, F-27
"""

import csv
import json
from pathlib import Path

from meritum_worker.observability.constants import CSV_JSON_COLUMNS, MIN_EVAL_CASES
from meritum_worker.observability.errors import TooFewCasesError
from meritum_worker.observability.models import GoldenSet


def load_eval_cases(path: Path) -> GoldenSet:
    """Read and validate a case file for an evaluation run.

    A ``.csv`` file has one column per case field; empty cells are missing
    fields and ``sources`` and ``injection`` hold JSON. Any other file is a
    JSON list. The case count is checked before the cases themselves.

    Args:
        path: The case file.

    Returns:
        The validated cases.

    Raises:
        TooFewCasesError: The file holds fewer than MIN_EVAL_CASES cases.
        OSError: The file cannot be read.
        json.JSONDecodeError: The file, or a CSV cell meant to hold JSON, is not JSON.
        pydantic.ValidationError: A case or a reference between cases is invalid.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """  # ruff: ignore[docstring-extraneous-exception]  # raised by the readers and model_validate
    is_csv = path.suffix.lower() == ".csv"
    rows = _read_csv(path) if is_csv else json.loads(path.read_text("utf-8"))
    count = len(rows) if isinstance(rows, list) else 0
    if count < MIN_EVAL_CASES:
        raise TooFewCasesError(count)
    return GoldenSet.model_validate(rows)


def _read_csv(path: Path) -> list[dict[str, object]]:
    # utf-8-sig: spreadsheets often start the file with a byte-order mark.
    with path.open(encoding="utf-8-sig", newline="") as file:
        return [_case(row) for row in csv.DictReader(file)]


def _case(row: dict[str, str]) -> dict[str, object]:
    return {
        key: json.loads(value) if key in CSV_JSON_COLUMNS else value
        for key, value in row.items()
        if value
    }
