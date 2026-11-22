import asyncio
import dataclasses
import io
from collections.abc import Callable
from pathlib import Path

import pypdfium2
from meritum_core.checks import CheckRequest
from meritum_core.jobs.contracts import CheckInput
from tests.link_pages import recorded_pages

from meritum_worker.checks import CheckDeps, CheckState
from meritum_worker.checks.constants import FETCH_URL_STEP
from meritum_worker.checks.steps import fetch_url

LINK = "https://example.gov.pl/rozporzadzenie.pdf"
REGULATION = Path(__file__).resolve().parents[1] / "corpus" / "fixtures" / "api"


def scan_without_text() -> bytes:
    document = pypdfium2.PdfDocument.new()
    document.new_page(595, 842)
    data = io.BytesIO()
    document.save(data)
    document.close()
    return data.getvalue()


def _fetched(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps], pdf: bytes
) -> CheckState:
    request = CheckRequest(channel="web", url=LINK)
    state = CheckState(
        check_id="check-1", job=make_job().model_copy(update={"request": request})
    )
    deps = dataclasses.replace(make_deps(), pages=recorded_pages({LINK: pdf}))
    return asyncio.run(fetch_url(state, deps))


def test_a_pdf_link_is_read_like_a_page(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    pdf = (REGULATION / "sejm-du-2025-1242.pdf").read_bytes()
    out = _fetched(make_job, make_deps, pdf)
    assert "w wysokości 4806 zł." in (out.page_text or "")
    assert out.failed_steps == []
    assert out.limitations == []


def test_a_scanned_pdf_without_text_is_an_unread_link(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _fetched(make_job, make_deps, scan_without_text())
    assert out.page_text is None
    assert out.failed_steps == [FETCH_URL_STEP]
    (note,) = out.limitations
    assert note.startswith("Nie udało się otworzyć strony example.gov.pl")


def test_a_broken_pdf_is_an_unread_link(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _fetched(make_job, make_deps, b"%PDF-1.7 broken")
    assert out.failed_steps == [FETCH_URL_STEP]
