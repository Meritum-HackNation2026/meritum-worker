"""Steps of the English source scenario in features/corpus.feature.

The only evidence is an English EUR-Lex page found by live search; the model is
the core stub with recorded answers, so no network.
"""

from behave import given, then, when
from behave.runner import Context
from live_search_steps import deps_with, run_check_on

TEXT = "Rozporządzenie o pomocy państwa weszło w życie 5 stycznia 2026"
URL = "https://eur-lex.europa.eu/eli/reg/2026/1/oj"
QUERIES = 2
QUOTE = "This Regulation shall enter into force on 5 January 2026."


@given("twierdzenie po polsku i jedyny dowód w dokumencie EUR-Lex po angielsku")
def english_only_evidence(context: Context) -> None:
    deps_with(
        context,
        f"Regulation on state aid. Article 9. {QUOTE}",
        url=URL,
        name="eurlex",
    )


@when("system bada twierdzenie")
def check_runs(context: Context) -> None:
    run_check_on(context, TEXT)


@then('cytat jest w oryginale z Source.language "{language}", a wyjaśnienie po polsku')
def quote_in_original(context: Context, language: str) -> None:
    assert context.result.status == "done"
    (claim,) = context.result.claims
    (citation,) = claim.citations
    assert citation.fragment == QUOTE
    assert citation.source.language == language
    assert "angielsku" in claim.explanation


@then("wyszukiwanie na żywo dostało zapytanie po polsku i po angielsku")
def both_queries_sent(context: Context) -> None:
    assert context.record.web_search_calls == QUERIES
