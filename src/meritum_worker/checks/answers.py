"""What the model answers in write_answer.

Features:
    US-SPR-01, F-22
"""

from meritum_core.checks.contracts import ClaimResult
from pydantic import BaseModel


class AnswerDraft(BaseModel):
    """What the model answers in write_answer, before the CheckResult rules apply.

    Attributes:
        claims: one result per claim.
        limitations: what the check could not cover.

    Features:
        US-SPR-01, F-22
    """

    claims: list[ClaimResult]
    limitations: list[str]
