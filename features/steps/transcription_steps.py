"""Steps of the audio scenarios in features/checks.feature.

The recording lies in the in-memory blob store and the core stub transcriber
answers; no network, no database.
"""

import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.checks.transcription import Transcript
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.blobs import (
    BlobKind,
)
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import (
    CheckDeps,
    FakePageFetcher,
    InlineCheckRuntime,
    audio_ports,
    ogg_opus,
    run_check,
)
from meritum_worker.checks.constants import UNSUPPORTED_AUDIO_FORMAT_MESSAGE

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CHECK_ID = "check-behave-audio"
RECEIVED_AT = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def _given_audio(context: Context, data: bytes, transcript: str | None) -> None:
    fixture = None
    if transcript is not None:
        fixture = Path(tempfile.mkdtemp()) / "transcript.json"
        answer = Transcript(text=transcript, language="pl-PL")
        fixture.write_text(answer.model_dump_json())
    ports = audio_ports(fixture)
    llm = LlmSettings(
        provider=LlmProvider.STUB, stub_fixtures=FIXTURES / "llm_stub_answer.json"
    )
    context.deps = CheckDeps(
        llm=build_llm(llm),
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **ports,
    )
    blobs = ports["blobs"]
    ref = asyncio.run(
        blobs.put(
            data,
            kind=BlobKind.AUDIO,
            content_type="audio/ogg",
            expires_at=RECEIVED_AT + timedelta(days=30),
        )
    )
    context.audio_id = ref.blob_id
    context.transcript = transcript


@given('plik OGG z Opus z nagraniem "{text}"')
def ogg_with_speech(context: Context, text: str) -> None:
    _given_audio(context, ogg_opus(seconds=8), text)


@given("dostawca transkrypcji zwraca błąd")
def transcription_fails(context: Context) -> None:
    _given_audio(context, ogg_opus(seconds=8), None)


@given("plik w formacie, którego port nie obsługuje")
def unsupported_format(context: Context) -> None:
    _given_audio(context, b"not an audio file at all", "nieważne")


@when("workflow sprawdzania działa")
def check_runs(context: Context) -> None:
    job = CheckInput(
        request=CheckRequest(channel="web", audio_id=context.audio_id),
        session_id="session-behave-audio",
        received_at=RECEIVED_AT,
    )
    context.runtime = InlineCheckRuntime()
    output = asyncio.run(
        run_check(job.model_dump(mode="json"), CHECK_ID, context.deps, context.runtime)
    )
    context.result = output.result


@then(
    "krok transcribe_audio kończy się stanem done, "
    "a twierdzenie z transkrypcji dostaje werdykt"
)
def transcribed_and_judged(context: Context) -> None:
    steps = {s.code: s.status for s in context.runtime.published[-1].steps}
    assert steps["transcribe_audio"] == "done", steps
    assert context.result.status == "done"
    assert all(claim.verdict for claim in context.result.claims)
    assert context.result.claims


@then("wynik zawiera transkrypcję oznaczoną jako automatyczna")
def result_has_transcript(context: Context) -> None:
    # CheckResult.transcript is by contract the automatic transcript.
    assert context.result.transcript == context.transcript


@then("wynik ma stan technical_failure")
def result_is_failure(context: Context) -> None:
    assert context.result.status == "technical_failure"
    assert context.result.failure_code == "transcription_failed"


@then("wynik ma stan out_of_scope z komunikatem, co można wysłać zamiast")
def result_out_of_scope(context: Context) -> None:
    assert context.result.status == "out_of_scope"
    assert context.result.message == UNSUPPORTED_AUDIO_FORMAT_MESSAGE
    assert not context.result.claims
