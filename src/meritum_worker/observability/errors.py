"""Errors of the observability slice.

Features:
    US-OBS-05, F-27
"""

from meritum_worker.observability.constants import MIN_EVAL_CASES


class TooFewCasesError(ValueError):
    """An evaluation file holds fewer cases than MIN_EVAL_CASES.

    Args:
        count: How many cases the file holds.

    Features:
        US-OBS-05, F-27
    """

    def __init__(self, count: int) -> None:
        super().__init__(
            f"an evaluation file needs at least {MIN_EVAL_CASES} cases, got {count}"
        )
