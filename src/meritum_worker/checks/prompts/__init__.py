"""Instructions of the check workflow's model calls.

Features:
    US-SPR-01, US-SPR-03, US-SPR-07, F-07, F-22, ADR-05, ADR-12
"""

from meritum_worker.checks.prompts.constants import (
    ANSWER_INSTRUCTIONS,
    EXTRACTION_INSTRUCTIONS,
    PUBLISHED_ON_INSTRUCTIONS,
)

__all__ = [
    "ANSWER_INSTRUCTIONS",
    "EXTRACTION_INSTRUCTIONS",
    "PUBLISHED_ON_INSTRUCTIONS",
]
