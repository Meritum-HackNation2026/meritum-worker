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
        The validated cases; pydantic's ValidationError names any invalid case
        or reference between cases.

    Features:
        US-OBS-04, F-27
    """
    return GoldenSet.model_validate_json(path.read_text(encoding="utf-8"))
