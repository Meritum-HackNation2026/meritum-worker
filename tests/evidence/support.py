"""Shared setup of the evidence tests: a dated fact and in-process ports."""

from datetime import UTC, date, datetime

from meritum_core.checks import CheckRequest
from meritum_core.checks.contracts import ClaimDateSource
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.evidence import SourceDocument
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmPort

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    ExtractedClaim,
    FakePageFetcher,
    audio_ports,
    corpus_ports,
    web_ports,
)

CLAIM = "Płaca minimalna wynosi 4806 zł"


def deps(llm: LlmPort) -> CheckDeps:
    return CheckDeps(
        llm=llm,
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **corpus_ports(),
        **web_ports(),
    )


def state_with(
    text: str,
    evidence: list[SourceDocument],
    claim: str = CLAIM,
    claim_date: date = date(2026, 1, 1),
    claim_date_source: ClaimDateSource = "text",
) -> CheckState:
    job = CheckInput(
        request=CheckRequest(channel="web", text=text),
        received_at=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
        session_id="session-1",
    )
    fact = ExtractedClaim(
        claim=claim,
        kind="fact",
        explanation="Twierdzenie o kwocie, które da się sprawdzić.",
        claim_date=claim_date,
        claim_date_source=claim_date_source,
    )
    return CheckState(check_id="check-1", job=job, claims=[fact], evidence=evidence)
