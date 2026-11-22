"""Models and ports of the moderation slice.

Features:
    US-MOD-01, US-MOD-02, F-24, ADR-22
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from meritum_core.checks import CheckRecordRepository
from meritum_core.moderation import (
    HighRiskTopicRepository,
    ModeratorCaseRepository,
    StaffRepository,
)
from meritum_core.shared.embeddings import EmbeddingsPort

type Trigger = Literal["recommended_clicked", "user_dispute", "cache_hit", "unanswered"]
"""What hands a claim over: a click, a dispute, a repeat from the result cache, or
the check itself finding the claim unanswered."""


@dataclass(frozen=True, slots=True)
class PastClaim:
    """An unanswered claim of an earlier finished check.

    Attributes:
        check_id: the check that asked it.
        claim: the claim text.

    Features:
        US-MOD-02, F-24
    """

    check_id: str
    claim: str


class CheckResults(Protocol):
    """What finished checks answered (port); the worker reads it from DBOS.

    Features:
        US-MOD-01, US-MOD-02, F-24
    """

    async def claim(self, check_id: str, claim_index: int) -> str | None:
        """Read the text of one claim of a finished check.

        Args:
            check_id: the check's id.
            claim_index: the claim's position in its result.

        Returns:
            The claim, or None when the check is unfinished or has no such claim.
        """
        ...

    async def unanswered_since(self, since: datetime) -> Sequence[PastClaim]:
        """List the unanswered claims of checks that started after ``since``.

        Args:
            since: the window's start.

        Returns:
            The claims, latest check first.
        """
        ...


@dataclass(frozen=True, slots=True)
class Referral:
    """One claim handed to the moderators.

    Attributes:
        claim: the claim text.
        check_id: the check that asked it.
        asker: the session or account that asked.
        trigger: what hands it over.
        now: the time of the hand-over.
        justification: the masked reason of a dispute.

    Features:
        US-MOD-01, US-MOD-02, US-MOD-06, F-24
    """

    claim: str
    check_id: str
    asker: str
    trigger: Trigger
    now: datetime
    justification: str | None = None


@dataclass(frozen=True, slots=True)
class ModerationDeps:
    """Ports of moderator cases, built once by ``build_moderation_deps``.

    Attributes:
        cases: where cases are kept.
        topics: the admin's high-risk list.
        staff: the panel accounts.
        records: the check records, for who asked.
        embeddings: similarity of claims and topics.
        results: what finished checks answered.
        admin_emails: the configured administrators; moderators too.
        lock: serialises case writes in this process.

    Features:
        US-MOD-01, US-MOD-02, F-24, ADR-35
    """

    cases: ModeratorCaseRepository
    topics: HighRiskTopicRepository
    staff: StaffRepository
    records: CheckRecordRepository
    embeddings: EmbeddingsPort
    results: CheckResults
    admin_emails: frozenset[str] = frozenset()
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
