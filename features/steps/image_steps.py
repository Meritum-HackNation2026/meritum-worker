"""Steps of the image scenarios in features/checks.feature.

The image lies in the in-memory blob store and the core stub OCR answers; no
network, no database.
"""

import asyncio
import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.blobs import BlobKind
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import (
    CheckDeps,
    FakePageFetcher,
    InlineCheckRuntime,
    audio_ports,
    corpus_ports,
    image_ports,
    png,
    run_check,
    web_ports,
)
from meritum_worker.checks.constants import IMAGE_DATE_NOTE

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
RECEIVED_AT = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def _given_image(context: Context, data: bytes, text: str | None) -> None:
    ports = image_ports(text)
    llm = LlmSettings(
        provider=LlmProvider.STUB, stub_fixtures=FIXTURES / "llm_stub_answer.json"
    )
    deps = CheckDeps(
        llm=build_llm(llm),
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **web_ports(),
        **corpus_ports(),
    )
    context.deps = dataclasses.replace(deps, **ports)
    ref = asyncio.run(
        ports["blobs"].put(
            data,
            kind=BlobKind.IMAGE,
            content_type="image/png",
            expires_at=RECEIVED_AT + timedelta(days=30),
        )
    )
    context.image_id = ref.blob_id


@given('zdjęcie z tekstem "{text}"')
def image_with_text(context: Context, text: str) -> None:
    _given_image(context, png(), text)


@given("dostawca OCR zwraca błąd")
def ocr_fails(context: Context) -> None:
    _given_image(context, png(), None)


@given("plik, który nie jest obrazem PNG, JPEG ani WebP")
def not_an_image(context: Context) -> None:
    _given_image(context, b"not an image at all", "nieważne")


@when("workflow sprawdza obraz")
def image_check_runs(context: Context) -> None:
    job = CheckInput(
        request=CheckRequest(channel="web", image_id=context.image_id),
        session_id="session-behave-image",
        received_at=RECEIVED_AT,
    )
    context.runtime = InlineCheckRuntime()
    output = asyncio.run(
        run_check(
            job.model_dump(mode="json"),
            "check-behave-image",
            context.deps,
            context.runtime,
        )
    )
    context.result = output.result


@then("twierdzenie z OCR dostaje werdykt")
def ocr_claim_judged(context: Context) -> None:
    assert context.result.status == "done", context.result
    assert context.result.claims
    assert all(claim.verdict for claim in context.result.claims)


@then("odpowiedź mówi, że nie szukano wcześniejszych wystąpień obrazu")
def image_search_not_run(context: Context) -> None:
    assert "image_search_not_run" in context.result.limitation_codes


@then("odpowiedź mówi, że data na obrazie nie potwierdza daty publikacji")
def image_date_does_not_confirm(context: Context) -> None:
    assert IMAGE_DATE_NOTE in context.result.limitations


@then("wynik obrazu ma stan technical_failure")
def image_result_is_failure(context: Context) -> None:
    assert context.result.status == "technical_failure"


@then("wynik obrazu ma stan out_of_scope z kodem image i kodem ograniczenia")
def image_result_out_of_scope(context: Context) -> None:
    assert context.result.status == "out_of_scope"
    assert context.result.out_of_scope_code == "image"
    assert context.result.limitation_codes == ["image_format_unsupported"]
