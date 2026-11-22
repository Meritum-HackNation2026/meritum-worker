"""Evidence slice of the worker: per-citation stance and the verdict from core rules.

Public API: re-exports only.

Features:
    US-ZRD-01, US-ZRD-04, US-ZRD-07, US-ZRD-10, F-15, F-16, F-34
"""

from meritum_worker.evidence.constants import (
    SANCTIONS_WORKFLOW,
    STANCE_INSTRUCTIONS,
)
from meritum_worker.evidence.fakes import RecordedLlm, document
from meritum_worker.evidence.models import (
    AssessedCitation,
    ClaimExplanation,
    Judgement,
    ReviewMatch,
    StanceJudgement,
    VerifiedCitation,
)
from meritum_worker.evidence.reviews import review_matches, split_reviews
from meritum_worker.evidence.sanctions import (
    SanctionedEntity,
    SanctionsList,
    load_sanctions,
    refresh_sanctions,
    sanctions_from_env,
)
from meritum_worker.evidence.stance import assess_stance, stance_prompt
from meritum_worker.evidence.verdict import (
    judge,
    resolve_check_claim_date,
    with_validity,
)

__all__ = [
    "SANCTIONS_WORKFLOW",
    "STANCE_INSTRUCTIONS",
    "AssessedCitation",
    "ClaimExplanation",
    "Judgement",
    "RecordedLlm",
    "ReviewMatch",
    "SanctionedEntity",
    "SanctionsList",
    "StanceJudgement",
    "VerifiedCitation",
    "assess_stance",
    "document",
    "judge",
    "load_sanctions",
    "refresh_sanctions",
    "resolve_check_claim_date",
    "review_matches",
    "sanctions_from_env",
    "split_reviews",
    "stance_prompt",
    "with_validity",
]
