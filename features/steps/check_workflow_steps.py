"""Steps of the `check` workflow scenarios in features/checks.feature.

They run the workflow on the core stub model and the in-memory record repository,
with steps called inline instead of through DBOS; no network, no database.
"""

from datetime import date, timedelta

from behave import given, then, when
from behave.runner import Context
from check_support import CHECK_ID, DEFAULT_TEXT, RECEIVED_AT, deps, run
from meritum_core.checks.contracts import CheckRecord
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    LoginWallError,
)

from meritum_worker.checks import (
    FailingCheckRuntime,
    FakePageFetcher,
)
from meritum_worker.checks.constants import TECHNICAL_FAILURE_CODE


@given("worker działa z MERITUM_LLM_PROVIDER=stub")
def worker_runs_on_stub(context: Context) -> None:
    context.deps = deps("llm_stub_answer.json")


@given("stub zwraca wynik niezgodny z regułami kontraktu")
def stub_breaks_contract(context: Context) -> None:
    context.deps = deps("llm_stub_broken_answer.json")


@given("krok workflowu sprawdzania rzuca wyjątek")
def check_step_raises(context: Context) -> None:
    context.deps = deps("llm_stub_answer.json")
    context.runtime = FailingCheckRuntime("search_web")


@when('workflow "check" dostaje CheckRequest z tekstem "{text}"')
def check_gets_text(context: Context, text: str) -> None:
    run(context, text)


@when("workflow buduje CheckResult")
def check_builds_result(context: Context) -> None:
    run(context, DEFAULT_TEXT)


@when("workflow kończy się błędem")
def workflow_fails(context: Context) -> None:
    try:
        run(context, DEFAULT_TEXT)
    except RuntimeError as error:
        context.workflow_error = error


@then("workflow kończy się stanem done z CheckResult zgodnym z kontraktem")
def check_is_done(context: Context) -> None:
    result = context.result.result
    assert result.status == "done"
    assert result.check_id == CHECK_ID
    final = context.runtime.published[-1]
    assert final.result == result
    assert {step.status for step in final.steps} == {"done", "skipped"}


@then(
    "CheckRecord ma question_masked, channel, received_at, answered_at, "
    "corpus_version, verdicts, source_ids, escalation i retention_until"
)
def record_is_complete(context: Context) -> None:
    record = context.record
    assert isinstance(record, CheckRecord)
    assert record.question_masked == DEFAULT_TEXT
    assert record.channel == "web"
    assert record.received_at == RECEIVED_AT
    assert record.answered_at >= RECEIVED_AT
    assert record.corpus_version
    assert record.verdicts == ["insufficient_evidence"]
    assert record.source_ids == []
    assert record.escalation is None
    assert record.retention_until == RECEIVED_AT + timedelta(days=30)


@then("wynik ma stan technical_failure bez twierdzeń")
def result_is_technical_failure(context: Context) -> None:
    result = context.result.result
    assert result.status == "technical_failure"
    assert result.claims == []


@then("CheckRecord ma status technical_failure")
def record_is_technical_failure(context: Context) -> None:
    assert context.record.status == "technical_failure"
    assert context.record.verdicts == []


@then(
    "strumień postępu dostaje ten krok jako failed i końcowy status "
    "technical_failure z kodem awarii z kontraktu v4"
)
def failed_step_closes_with_technical_failure(context: Context) -> None:
    assert str(context.workflow_error) == "step failed"
    final = context.runtime.published[-1]
    failed = [step.code for step in final.steps if step.status == "failed"]
    assert failed == ["search_web"]
    assert final.result.status == "technical_failure"
    assert final.result.failure_code == TECHNICAL_FAILURE_CODE
    assert context.runtime.closed_after == len(context.runtime.published)


VERDICTS = {"nie podlega weryfikacji": "not_verifiable"}
EIGHT_FACTS = [f"W 2024 r. wskaźnik numer {i} wyniósł {i},5%." for i in range(1, 9)]
OPINION = "Rząd kompletnie sobie nie radzi."


@given('tekst "{text}" z nagranymi odpowiedziami modelu "{fixture}"')
def text_with_recorded_model(context: Context, text: str, fixture: str) -> None:
    context.input_text = text
    context.deps = deps(fixture)


@given('tekst z 8 twierdzeniami o faktach z nagranymi odpowiedziami modelu "{fixture}"')
def eight_facts_with_recorded_model(context: Context, fixture: str) -> None:
    text_with_recorded_model(context, " ".join(EIGHT_FACTS), fixture)


@when("system wyodrębnia twierdzenia")
def system_extracts_claims(context: Context) -> None:
    run(context, context.input_text)


@then("wynik ma stan done i {count:d} wyniki")
def result_is_done_with(context: Context, count: int) -> None:
    result = context.result.result
    assert result.status == "done"
    assert len(result.claims) == count


@then('opinia dostaje werdykt "{verdict}"')
def opinion_gets_verdict(context: Context, verdict: str) -> None:
    claims = context.result.result.claims
    opinion = next(c for c in claims if c.claim == OPINION)
    assert opinion.verdict == VERDICTS[verdict]


@then("sprawdza 5 twierdzeń, a pozostałe 3 są wymienione w limitations")
def five_checked_three_in_limitations(context: Context) -> None:
    result = context.result.result
    assert [c.claim for c in result.claims] == EIGHT_FACTS[:5]
    for skipped in EIGHT_FACTS[5:]:
        assert skipped in result.limitations


@then("wynik ma stan needs_clarification bez twierdzeń, tylko z komunikatem")
def result_needs_clarification(context: Context) -> None:
    result = context.result.result
    assert result.status == "needs_clarification"
    assert result.claims == []
    assert result.message


@then('twierdzenie ma claim_date {day} i claim_date_source "{source}"')
def claim_has_date(context: Context, day: str, source: str) -> None:
    (claim,) = context.result.result.claims
    assert claim.claim_date == date.fromisoformat(day)
    assert claim.claim_date_source == source


FACEBOOK_POST = "https://www.facebook.com/groups/1/posts/2"
ARTICLE_TEXT = "Inflacja w październiku wyniosła 2,8%. Bezrobocie 03.2025: 5,3%."


@given("link do posta na Facebooku wymagającego logowania")
def facebook_post_behind_login(context: Context) -> None:
    wall = LoginWallError(FetchFailureReason.LOGIN_WALL)
    context.deps = deps("llm_stub_answer.json", FakePageFetcher(wall))
    context.link = FACEBOOK_POST


@given("link do publicznego artykułu z datą publikacji {day}")
def article_with_date(context: Context, day: str) -> None:
    page = FetchedPage(
        url="https://example.com/artykul",
        content_type="text/html",
        untrusted_text=ARTICLE_TEXT,
        published_at=date.fromisoformat(day),
    )
    context.deps = deps("claims_article.json", FakePageFetcher(page))
    context.link = page.url
    context.published_at = page.published_at
    # The check comes in after the page was published, else its date is dropped.
    context.received_at = RECEIVED_AT.replace(year=date.fromisoformat(day).year + 1)


@when("workflow sprawdza link")
def check_gets_link(context: Context) -> None:
    run(context, url=context.link)


@then(
    "krok fetch_url kończy się stanem done, a twierdzenia z tekstu artykułu mają"
    ' claim_date_source "{source}", gdy tekst nie podaje innej daty'
)
def article_claims_take_its_date(context: Context, source: str) -> None:
    steps = {step.code: step.status for step in context.runtime.published[-1].steps}
    assert steps["fetch_url"] == "done"
    undated, dated = context.result.result.claims
    assert undated.claim_date == context.published_at
    assert undated.claim_date_source == source
    # The second claim names its own month in the text (claims_article.json).
    assert dated.claim_date_source == "text"


@then(
    'wynik ma stan technical_failure z kodem "{code}" i prośbą o wklejenie tekstu,'
    " bez werdyktu"
)
def result_asks_to_paste_text(context: Context, code: str) -> None:
    result = context.result.result
    assert result.status == "technical_failure"
    assert result.failure_code == code
    assert not (result.message or "").startswith("status_hint.")
    assert result.claims == []
    assert context.deps.pages.calls[0][0] == FACEBOOK_POST


@given("wklejony tekst bez adresu")
def pasted_text_without_link(context: Context) -> None:
    context.deps = deps("llm_stub_answer.json")


@when("workflow publikuje postęp")
def check_publishes_progress(context: Context) -> None:
    run(context, DEFAULT_TEXT)


@then("krok fetch_url ma stan {status}")
def fetch_url_has_status(context: Context, status: str) -> None:
    for published in context.runtime.published[2:]:
        steps = {step.code: step.status for step in published.steps}
        assert steps["fetch_url"] == status
    assert context.deps.pages.calls == []
