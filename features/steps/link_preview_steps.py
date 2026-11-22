"""Steps of the video, post and PDF link scenarios in checks.feature (worker#288)."""

import dataclasses

from behave import given, then
from behave.runner import Context
from check_support import FIXTURES, deps
from tests.checks.test_pdf_links import LINK as PDF_LINK
from tests.checks.test_pdf_links import REGULATION, scan_without_text
from tests.link_pages import recorded_pages

YOUTUBE = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
TIKTOK = "https://www.tiktok.com/@bbcnews/video/7438029934817946912"


def _given_page(context: Context, link: str, page: bytes, answers: str) -> None:
    pages = recorded_pages({link: page})
    context.deps = dataclasses.replace(deps(answers), pages=pages)
    context.link = link


def _given_link(context: Context, link: str, page: str, answers: str) -> None:
    _given_page(context, link, (FIXTURES / "links" / page).read_bytes(), answers)


@given("link do pliku PDF z rozporządzeniem o płacy minimalnej")
def pdf_link(context: Context) -> None:
    pdf = (REGULATION / "sejm-du-2025-1242.pdf").read_bytes()
    _given_page(context, PDF_LINK, pdf, "llm_stub_answer.json")


@given("link do pliku PDF, który jest skanem bez tekstu")
def scanned_pdf_link(context: Context) -> None:
    # The address of a file names no claim, so the model finds none.
    _given_page(context, PDF_LINK, scan_without_text(), "claims_none.json")


@then("sprawdzany jest tekst dokumentu PDF")
def pdf_text_checked(context: Context) -> None:
    assert context.result.result.status == "done"
    assert "w wysokości 4806 zł." in context.record.question_masked


@given("link do filmu na YouTube i nagraną stronę filmu")
def youtube_link(context: Context) -> None:
    _given_link(context, YOUTUBE, "youtube-watch.html", "llm_stub_answer.json")


@given("link do filmu na TikToku i nagraną stronę bez opisu")
def tiktok_link(context: Context) -> None:
    # The address of a video names no claim, so the model finds none.
    _given_link(context, TIKTOK, "tiktok-video.html", "claims_none.json")


@then("sprawdzany jest tytuł i opis filmu")
def title_and_description_checked(context: Context) -> None:
    assert context.result.result.status == "done"
    question = context.record.question_masked
    assert question.startswith("Me at the zoo")
    assert question.endswith("00:17 End")


@then("ograniczenia mówią, że nie oglądaliśmy nagrania")
def limitations_say_not_watched(context: Context) -> None:
    notes = [n for n in context.result.result.limitations if "nagrania" in n]
    assert len(notes) == 1


@then('wynik ma stan technical_failure z kodem "{code}"')
def result_is_failure_with_code(context: Context, code: str) -> None:
    result = context.result.result
    assert (result.status, result.failure_code) == ("technical_failure", code)
    assert result.claims == []
