"""Steps of the link-in-the-text scenarios in features/checks.feature (worker#256)."""

from behave import given, then
from behave.runner import Context
from check_support import deps
from meritum_core.corpus.fetching import FetchedPage, FetchPurpose, PaywallError

from meritum_worker.checks import FakePageFetcher

PAGE_TEXT = "Dwie rosyjskie rakiety spadły w Polsce podczas ataku na Ukrainę."


@given('publiczna strona pod adresem "{link}"')
def public_page_at(context: Context, link: str) -> None:
    page = FetchedPage(url=link, content_type="text/html", untrusted_text=PAGE_TEXT)
    context.deps = deps("llm_stub_answer.json", FakePageFetcher(page))
    context.link = link


@given('strona pod adresem "{link}" jest za paywallem')
def page_behind_paywall(context: Context, link: str) -> None:
    context.deps = deps("llm_stub_answer.json", FakePageFetcher(PaywallError()))
    context.link = link


def _step_status(context: Context, code: str) -> object:
    return {s.code: s.status for s in context.runtime.published[-1].steps}[code]


@then(
    "krok fetch_url kończy się stanem done, a strona spod adresu z tekstu"
    " została pobrana"
)
def page_from_the_text_was_fetched(context: Context) -> None:
    assert _step_status(context, "fetch_url") == "done"
    assert context.deps.pages.calls == [(context.link, FetchPurpose.USER_LINK)]
    assert context.result.result.status == "done"


@then("zapis sprawdzenia zachowuje pytanie razem z adresem")
def record_keeps_the_question(context: Context) -> None:
    assert context.record.question_masked.endswith(context.link)


@then("sprawdzany jest tekst strony")
def page_text_is_checked(context: Context) -> None:
    assert context.record.question_masked == PAGE_TEXT


@then("sprawdzenie kończy się stanem done z krokiem fetch_url w stanie failed")
def check_goes_on_without_the_page(context: Context) -> None:
    assert context.result.result.status == "done"
    assert _step_status(context, "fetch_url") == "failed"
    assert context.result.result.claims


@then('ograniczenia mówią, że strony "{host}" nie udało się otworzyć')
def limitations_say_page_unread(context: Context, host: str) -> None:
    notes = [n for n in context.result.result.limitations if host in n]
    assert len(notes) == 1
    assert "Nie udało się otworzyć" in notes[0]
