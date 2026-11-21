"""The one domain error of a failed provider: model, web search or transcription.

Features:
    US-BEZ-03, US-SPR-04, US-SPR-06, F-18
"""

from meritum_core.checks.contracts import FailureCode
from meritum_core.checks.transcription import TranscriptionUnavailableError
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.checks.constants import (
    STEP_FAILURE_CODES,
    TECHNICAL_FAILURE_CODE,
    TIMEOUT_REASON,
    TRANSCRIPTION_FAILED_CODE,
)


class ProviderFailureError(Exception):
    """A provider failed, timed out, hit its rate limit or has no key.

    Its text never holds the provider's own message, so no key name or
    provider name reaches the result or the record.

    Args:
        code: the contract v4 failure_code.
        reason: the retrieval error recorded, ``<step code>: <what>``.

    Features:
        US-BEZ-03, US-SPR-04, US-SPR-06, F-18
    """

    def __init__(self, code: FailureCode, reason: str) -> None:
        super().__init__(reason)
        self.code: FailureCode = code
        self.reason = reason


def provider_failure(step: str, error: Exception) -> ProviderFailureError | None:
    """Map a provider error or timeout of the step code ``step`` to the domain error.

    Args:
        step: the AnalysisStep code that failed.
        error: the error it raised.

    Returns:
        The domain error, the provider's own message dropped; None for any other
        error, which still fails the workflow.

    Features:
        US-BEZ-03, US-SPR-04, US-SPR-06, F-18
    """
    match error:
        case ProviderFailureError():
            return error
        case TimeoutError():
            code = STEP_FAILURE_CODES.get(step, TECHNICAL_FAILURE_CODE)
            return ProviderFailureError(code, f"{step}: {TIMEOUT_REASON}")
        case TranscriptionUnavailableError():
            code = TRANSCRIPTION_FAILED_CODE
        case ProviderUnavailableError():
            code = TECHNICAL_FAILURE_CODE
        case _:
            return None
    return ProviderFailureError(code, f"{step}: {code}")
