"""Moderation slice: moderator cases made automatically, grouping similar claims.

Features:
    US-MOD-01, US-MOD-02, US-MOD-03, US-MOD-06, F-24, ADR-22, ADR-35
"""

from meritum_worker.moderation.cases import refer
from meritum_worker.moderation.constants import (
    PANEL_LINK,
    SIMILARITY_WINDOW,
    UNANSWERED_VERDICT,
)
from meritum_worker.moderation.factory import build_moderation_deps
from meritum_worker.moderation.fakes import InMemoryCheckResults, ScriptedEmbeddings
from meritum_worker.moderation.grouping import similar_flags
from meritum_worker.moderation.models import (
    CheckResults,
    ModerationDeps,
    PastClaim,
    Referral,
)
from meritum_worker.moderation.recipients import case_recipients
from meritum_worker.moderation.workflow import run_escalate_claim

__all__ = [
    "PANEL_LINK",
    "SIMILARITY_WINDOW",
    "UNANSWERED_VERDICT",
    "CheckResults",
    "InMemoryCheckResults",
    "ModerationDeps",
    "PastClaim",
    "Referral",
    "ScriptedEmbeddings",
    "build_moderation_deps",
    "case_recipients",
    "refer",
    "run_escalate_claim",
    "similar_flags",
]
