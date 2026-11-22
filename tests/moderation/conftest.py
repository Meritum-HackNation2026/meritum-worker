import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from functools import wraps

import pytest
from meritum_core.checks.contracts import CheckRecord
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.moderation import HighRiskTopic
from meritum_core.moderation.fakes import (
    InMemoryHighRiskTopicRepository,
    InMemoryModeratorCaseRepository,
    InMemoryStaffRepository,
)
from meritum_core.shared.embeddings import Vector

from meritum_worker.moderation import (
    InMemoryCheckResults,
    ModerationDeps,
    Referral,
    ScriptedEmbeddings,
)

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)

type Make = Callable[..., ModerationDeps]
type Ask = Callable[..., Referral]


@pytest.fixture
def make() -> Make:
    def build(vectors: dict[str, Vector] | None = None) -> ModerationDeps:
        return ModerationDeps(
            cases=InMemoryModeratorCaseRepository(),
            topics=InMemoryHighRiskTopicRepository(),
            staff=InMemoryStaffRepository(),
            records=InMemoryCheckRecordRepository(),
            embeddings=ScriptedEmbeddings(vectors or {}),
            results=InMemoryCheckResults(),
        )

    return build


@pytest.fixture
def ask() -> Ask:
    def referral(claim: str, check_id: str, trigger: str = "unanswered") -> Referral:
        return Referral(claim, check_id, f"s_{check_id}_000", trigger, NOW)  # ty: ignore[invalid-argument-type]

    return referral


@pytest.fixture
def health() -> HighRiskTopic:
    return HighRiskTopic(name="zdrowie", keywords=["szczepion"])


def sync[**P, R](test: Callable[P, Coroutine[None, None, R]]) -> Callable[P, R]:
    """Run an async test body; the repo has no pytest async plugin."""

    @wraps(test)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        return asyncio.run(test(*args, **kwargs))

    return run


async def record(deps: ModerationDeps, check_id: str) -> None:
    """Save the record of a finished check asked by session ``s_<check_id>``."""
    await deps.records.save(
        CheckRecord(
            check_id=check_id,
            session_id=f"s_{check_id}_000",
            channel="web",
            received_at=NOW,
            answered_at=NOW,
            question_masked="pytanie",
            status="done",
            verdicts=[],
            source_ids=[],
            models=[],
            corpus_version="none",
            retention_until=NOW + timedelta(days=30),
        )
    )
