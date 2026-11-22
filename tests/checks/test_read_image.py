import asyncio
import dataclasses
from collections.abc import Callable
from datetime import date, timedelta

from meritum_core.checks import CheckRequest
from meritum_core.jobs.contracts import CheckInput
from meritum_core.shared.blobs import BlobKind

from meritum_worker.checks import CheckDeps, CheckState, image_ports, png
from meritum_worker.checks.image.constants import IMAGE_DATE_NOTE, READ_IMAGE_STEP
from meritum_worker.checks.steps import read_image

TEXT = "Od 1 grudnia zakaz wjazdu aut spalinowych do Warszawy. Opublikowano 12.11.2026."


def _state(job: CheckInput, deps: CheckDeps, data: bytes) -> CheckState:
    ref = asyncio.run(
        deps.blobs.put(
            data,
            kind=BlobKind.IMAGE,
            content_type="image/png",
            expires_at=job.received_at + timedelta(days=30),
        )
    )
    request = CheckRequest(channel="web", image_id=ref.blob_id)
    return CheckState(
        check_id="check-1", job=job.model_copy(update={"request": request})
    )


def _run(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    text: str | None = TEXT,
    data: bytes | None = None,
) -> CheckState:
    deps = dataclasses.replace(make_deps(), **image_ports(text))
    state = _state(make_job(), deps, png() if data is None else data)
    return asyncio.run(read_image(state, deps))


def test_read_image_keeps_text_date_and_says_no_search_ran(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _run(make_job, make_deps)
    assert out.result is None
    assert out.image_text == TEXT
    assert out.final_result().image_text == TEXT
    assert out.image_date == date(2026, 11, 12)
    assert out.question == TEXT
    codes = [code for code, _ in out.image_notes]
    assert codes == ["corpus_scope", "image_search_not_run"]
    assert IMAGE_DATE_NOTE in [text for _, text in out.image_notes]


def test_read_image_without_a_date_has_no_date_note(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _run(make_job, make_deps, text="Zakaz wjazdu aut spalinowych")
    assert out.image_date is None
    assert [code for code, _ in out.image_notes] == ["image_search_not_run"]


def test_read_image_skips_a_text_request(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    state = CheckState(check_id="check-1", job=make_job())
    out = asyncio.run(read_image(state, make_deps()))
    assert out.skipped_steps == [READ_IMAGE_STEP]


def test_unsupported_image_is_out_of_scope_with_its_limitation_code(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _run(make_job, make_deps, data=b"not an image")
    assert out.result is not None
    assert out.result.status == "out_of_scope"
    assert out.result.out_of_scope_code == "image"
    assert out.result.limitation_codes == ["image_format_unsupported"]


def test_oversized_image_names_the_size_limit(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _run(make_job, make_deps, data=png() + bytes(10 * 1024 * 1024))
    assert out.result is not None
    assert out.result.limitation_codes == ["image_too_large"]


def test_ocr_failure_is_a_technical_failure(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _run(make_job, make_deps, text=None)
    assert out.result is not None
    assert out.result.status == "technical_failure"


def test_image_without_text_needs_clarification(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _run(make_job, make_deps, text="   ")
    assert out.result is not None
    assert out.result.status == "needs_clarification"


def test_file_metadata_is_context_and_never_changes_the_text_or_date(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    small = _run(make_job, make_deps)
    big = _run(make_job, make_deps, data=png() + bytes(4096))
    assert small.image_info != big.image_info
    assert (small.image_text, small.image_date, small.image_notes) == (
        big.image_text,
        big.image_date,
        big.image_notes,
    )
