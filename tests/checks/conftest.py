from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus.fetching import PageFetcherPort
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    ExtractedClaim,
    FakePageFetcher,
)

FIXTURES = Path(__file__).resolve().parents[2] / "features" / "fixtures"
RECEIVED_AT = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def _deps(
    fixture: str | None = "llm_stub_answer.json",
    pages: PageFetcherPort | None = None,
) -> CheckDeps:
    path = None if fixture is None else FIXTURES / fixture
    settings = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=path)
    return CheckDeps(
        llm=build_llm(settings),
        records=InMemoryCheckRecordRepository(),
        pages=pages or FakePageFetcher(),
        pii=NullPiiGate(),
    )


def _job(**identity: str) -> CheckInput:
    return CheckInput(
        request=CheckRequest(channel="web", text="Płaca minimalna wynosi 4806 zł"),
        received_at=RECEIVED_AT,
        **(identity or {"session_id": "session-1"}),
    )


type MakeDeps = Callable[..., CheckDeps]
type MakeJob = Callable[..., CheckInput]


@pytest.fixture
def make_deps() -> MakeDeps:
    """Deps on the stub model with a fixture from features/fixtures (None: none).

    ``pages`` replaces the fetcher, which by default fails every link.
    """
    return _deps


@pytest.fixture
def make_job() -> MakeJob:
    """A web CheckInput; keyword arguments replace the session id."""
    return _job


@pytest.fixture
def state() -> CheckState:
    """A check whose input holds one extracted fact, as write_answer gets it."""
    fact = ExtractedClaim(
        claim="Płaca minimalna wynosi 4806 zł",
        kind="fact",
        explanation="Twierdzenie o kwocie, które da się sprawdzić.",
        claim_date=RECEIVED_AT.date(),
        claim_date_source="today",
    )
    return CheckState(check_id="check-1", job=_job(), claims=[fact])
