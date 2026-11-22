"""What the model answers in write_answer.

Features:
    US-SPR-01, F-22
"""

from pydantic import BaseModel

from meritum_worker.evidence import ClaimExplanation


class AnswerDraft(BaseModel):
    """What the model answers in write_answer, before the CheckResult rules apply.

    Attributes:
        claims: one explanation per fact, in order; the verdict comes from code.
        limitations: what the check could not cover.

    Features:
        US-SPR-01, F-22
    """

    claims: list[ClaimExplanation]
    limitations: list[str]
