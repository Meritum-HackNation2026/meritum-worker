"""Read an evaluation case file: JSON or CSV, at least MIN_EVAL_CASES cases.

Features:
    US-OBS-04, US-OBS-05, F-27
"""

import csv
import json
from pathlib import Path

from meritum_worker.observability.constants import CSV_JSON_COLUMNS, MIN_EVAL_CASES
from meritum_worker.observability.errors import TooFewCasesError
from meritum_worker.observability.golden import load_golden_set
from meritum_worker.observability.models import GoldenSet


def load_eval_cases(path: Path) -> GoldenSet:
    """Read and validate a case file for an evaluation run.

    A ``.csv`` file has one column per case field; empty cells are missing
    fields and ``sources`` and ``injection`` hold JSON. Any other file is JSON.

    Args:
        path: The case file.

    Returns:
        The validated cases.

    Raises:
        TooFewCasesError: The file holds fewer than MIN_EVAL_CASES cases.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """
    is_csv = path.suffix.lower() == ".csv"
    cases = _read_csv(path) if is_csv else load_golden_set(path)
    if len(cases.root) < MIN_EVAL_CASES:
        raise TooFewCasesError(len(cases.root))
    return cases


def _read_csv(path: Path) -> GoldenSet:
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return GoldenSet.model_validate([_case(row) for row in rows])


def _case(row: dict[str, str]) -> dict[str, object]:
    return {
        key: json.loads(value) if key in CSV_JSON_COLUMNS else value
        for key, value in row.items()
        if value
    }
