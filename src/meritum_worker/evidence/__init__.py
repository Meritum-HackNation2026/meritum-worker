"""Evidence slice of the worker: per-citation stance and the verdict from core rules.

Public API: re-exports only.

Features:
    US-ZRD-01, US-ZRD-04, US-ZRD-10, F-15, F-16
"""

from meritum_worker.evidence.constants import STANCE_INSTRUCTIONS
from meritum_worker.evidence.fakes import RecordedLlm, document
from meritum_worker.evidence.models import (
    AssessedCitation,
    ClaimExplanation,
    Judgement,
    StanceJudgement,
    VerifiedCitation,
)
from meritum_worker.evidence.stance import assess_stance, stance_prompt
from meritum_worker.evidence.verdict import (
    judge,
    resolve_check_claim_date,
    with_validity,
)

__all__ = [
    "STANCE_INSTRUCTIONS",
    "AssessedCitation",
    "ClaimExplanation",
    "Judgement",
    "RecordedLlm",
    "StanceJudgement",
    "VerifiedCitation",
    "assess_stance",
    "document",
    "judge",
    "resolve_check_claim_date",
    "stance_prompt",
    "with_validity",
]
