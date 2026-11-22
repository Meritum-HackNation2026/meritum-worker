"""What the model answers in write_answer.

Features:
    US-SPR-01, F-22
"""

import re

from pydantic import BaseModel

from meritum_worker.checks.constants import CODE_PATTERN, STANCE_LABELS, VERDICT_LABELS
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


def plain_text(text: str) -> str:
    """Replace verdict and stance codes in a model text with their Polish names.

    The prompt forbids codes; this is the check after it, so a code that slips
    through never reaches the citizen.

    Args:
        text: an explanation, unresolved or limitation written by the model.

    Returns:
        The text with each code replaced by its Polish name; verdicts are quoted.

    Features:
        US-SPR-01, F-22
    """

    def name(match: re.Match[str]) -> str:
        code = match[1]
        return (
            f"„{VERDICT_LABELS[code]}”"
            if code in VERDICT_LABELS
            else STANCE_LABELS[code]
        )

    return CODE_PATTERN.sub(name, text)
