"""Load a case file (the golden set or the jury's file in the same format).

Features:
    US-OBS-04, F-27
"""

from pathlib import Path

from meritum_worker.observability.models import GoldenSet


def load_golden_set(path: Path) -> GoldenSet:
    """Read and validate a JSON case file.

    Args:
        path: The JSON file, a list of cases.

    Returns:
        The validated cases.

    Raises:
        OSError: The file cannot be read.
        pydantic.ValidationError: A case or a reference between cases is invalid.

    Features:
        US-OBS-04, F-27
    """  # ruff: ignore[docstring-extraneous-exception]  # raised by read_text and model_validate_json
    return GoldenSet.model_validate_json(path.read_text(encoding="utf-8"))
