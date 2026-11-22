"""Steps of the EU sanctions warning scenario in features/evidence.feature.

The check runs inline on a recorded model answer and the local list file.
"""

from dataclasses import replace

from behave import given, then, when
from behave.runner import Context
from check_support import FIXTURES, deps, run
from meritum_core.corpus.fetching import FetchedPage

from meritum_worker.checks import FakePageFetcher
from meritum_worker.evidence import load_sanctions

LINK = "https://www.agencja-sankcyjna.example/news/1"
BASIS = "https://eur-lex.europa.eu/eli/reg/2022/350/oj"


@given(
    "sprawdzany link prowadzi do domeny podmiotu z aktualnym wpisem na liście"
    " sankcji UE"
)
def link_to_listed_entity(context: Context) -> None:
    page = FetchedPage(
        url=LINK,
        content_type="text/html",
        untrusted_text="Inflacja w październiku wyniosła 2,8%.",
    )
    plain = deps("claims_article.json", FakePageFetcher(page))
    context.plain_deps = plain
    context.deps = replace(
        plain, sanctions=load_sanctions(FIXTURES / "sanctions_list.json")
    )


@when("system buduje wynik")
def build_result(context: Context) -> None:
    run(context, url=LINK)
    context.with_warning = context.result.result
    context.deps = context.plain_deps
    run(context, url=LINK)
    context.without_warning = context.result.result


@then('source_warning ma code "{code}", nazwę podmiotu i basis_url do wpisu')
def warning_names_entity(context: Context, code: str) -> None:
    warning = context.with_warning.source_warning
    assert warning is not None
    assert (warning.code, warning.entity) == (code, "Przykładowa Agencja Informacyjna")
    assert str(warning.basis_url) == BASIS


@then("werdykt jest taki sam jak bez ostrzeżenia")
def verdict_unchanged(context: Context) -> None:
    verdicts = lambda r: [c.verdict for c in r.claims]  # ruff: ignore[lambda-assignment]
    assert context.without_warning.source_warning is None
    assert verdicts(context.with_warning) == verdicts(context.without_warning)
