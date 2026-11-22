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


class CassetteMissError(LookupError):
    """A replayed run asked for an answer the cassette did not record.

    The run then differs from the recording (other cases, prompts or code), so
    the check ends as a technical failure instead of reaching a provider.

    Args:
        key: The request key that has no recorded answer left.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    def __init__(self, key: str) -> None:
        super().__init__(f"no recorded answer left for request {key}")
