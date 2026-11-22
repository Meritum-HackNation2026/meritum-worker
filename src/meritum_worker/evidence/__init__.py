"""Evidence slice of the worker: validity, strength and verdict from core rules.

Public API: re-exports only.

Features:
    US-ZRD-04, US-ZRD-05, US-ZRD-10, F-15, ADR-05, ADR-25
"""

from meritum_worker.evidence.models import Judgement, VerifiedCitation
from meritum_worker.evidence.verdict import (
    judge,
    resolve_check_claim_date,
    with_validity,
)

__all__ = [
    "Judgement",
    "VerifiedCitation",
    "judge",
    "resolve_check_claim_date",
    "with_validity",
]
