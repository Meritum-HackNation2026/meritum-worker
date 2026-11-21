"""Shared setup of the `check` steps: stub model, in-memory records, inline runtime."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import (
    CheckDeps,
    FakePageFetcher,
    InlineCheckRuntime,
    audio_ports,
    run_check,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CHECK_ID = "check-behave-1"
RECEIVED_AT = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
DEFAULT_TEXT = "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł"


def deps(fixture: str, pages: FakePageFetcher | None = None) -> CheckDeps:
    settings = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=FIXTURES / fixture)
    return CheckDeps(
        llm=build_llm(settings),
        records=InMemoryCheckRecordRepository(),
        pages=pages or FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
    )


def run(context: Context, text: str | None = None, url: str | None = None) -> None:
    job = CheckInput(
        request=CheckRequest(channel="web", text=text, url=url),
        session_id="session-behave-1",
        received_at=RECEIVED_AT,
    )
    if not hasattr(context, "runtime"):
        context.runtime = InlineCheckRuntime()
    context.result = asyncio.run(
        run_check(job.model_dump(mode="json"), CHECK_ID, context.deps, context.runtime)
    )
    context.record = asyncio.run(context.deps.records.get(CHECK_ID))
