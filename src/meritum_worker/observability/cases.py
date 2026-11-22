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


def parse_eval_cases(data: bytes, name: str) -> GoldenSet:
    """Read and validate case bytes for an evaluation run.

    Args:
        data: the file's bytes.
        name: the file name; a ``.csv`` suffix selects the CSV reader.

    Returns:
        The validated cases.

    Raises:
        TypeError: The JSON file is not a list of cases.
        TooFewCasesError: The file holds fewer than MIN_EVAL_CASES cases.
        json.JSONDecodeError: The file, or a CSV cell meant to hold JSON, is not JSON.
        pydantic.ValidationError: A case or a reference between cases is invalid.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-31
    """  # ruff: ignore[docstring-extraneous-exception]  # raised by the readers and model_validate
    is_csv = Path(name).suffix.lower() == ".csv"
    rows = _read_csv_bytes(data) if is_csv else json.loads(data.decode("utf-8"))
    if not isinstance(rows, list):
        msg = "a case file holds a list of cases"
        raise TypeError(msg)
    if len(rows) < MIN_EVAL_CASES:
        raise TooFewCasesError(len(rows))
    return GoldenSet.model_validate(rows)


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
        TypeError: The JSON file is not a list of cases.
        TooFewCasesError: The file holds fewer than MIN_EVAL_CASES cases.
        OSError: The file cannot be read.
        json.JSONDecodeError: The file, or a CSV cell meant to hold JSON, is not JSON.
        pydantic.ValidationError: A case or a reference between cases is invalid.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """  # ruff: ignore[docstring-extraneous-exception]  # raised by the readers and model_validate
    return parse_eval_cases(path.read_bytes(), path.name)


def _read_csv_bytes(data: bytes) -> list[dict[str, object]]:
    text = data.decode("utf-8-sig")
    return [_case(row) for row in csv.DictReader(text.splitlines())]


def _case(row: dict[str, str]) -> dict[str, object]:
    return {
        key: json.loads(value) if key in CSV_JSON_COLUMNS else value
        for key, value in row.items()
        if value
    }
