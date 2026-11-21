"""Steps of the research agents in features/checks.feature: parallel and streamed."""

import dataclasses
from datetime import UTC, date, datetime

from behave import given, then, when
from behave.runner import Context
from check_support import DEFAULT_TEXT, deps, run
from meritum_core.corpus import Passage

from meritum_worker.checks import FakeCorpusSearch
from meritum_worker.checks.constants import MAX_PARALLEL_CLAIMS

FOUR_FACTS = [f"W 2024 r. wskaźnik numer {i} wyniósł {i},5%." for i in range(1, 5)]
PASSAGE = Passage(
    passage_id="p1",
    source_id="gus",
    text="W 2024 r. wskaźnik wyniósł 1,5%.",
    published_on=date(2025, 1, 15),
    fetched_at=datetime(2026, 1, 5, tzinfo=UTC),
)


@given("tekst z 4 twierdzeniami")
def four_claims(context: Context) -> None:
    context.corpus = FakeCorpusSearch([PASSAGE])
    context.deps = dataclasses.replace(
        deps("claims_four_facts.json"), corpus=context.corpus, corpus_version="v1"
    )


@when("workflow uruchamia agenty badawcze")
def research_agents_run(context: Context) -> None:
    run(context, " ".join(FOUR_FACTS))


@then("najwyżej 3 twierdzenia są badane jednocześnie")
def at_most_three_at_once(context: Context) -> None:
    assert len(context.corpus.queries) == len(FOUR_FACTS)
    assert context.corpus.most_at_once == MAX_PARALLEL_CLAIMS


@then("AnalysisStatus pokazuje kilka kroków w stanie active naraz")
def several_steps_active(context: Context) -> None:
    active = [
        [step.code for step in status.steps if step.status == "active"]
        for status in context.runtime.published
    ]
    research = ["search_corpus", "search_web", "search_fact_checks"]
    assert research in active, active


@given("agent główny strumieniuje wstępną odpowiedź")
def main_agent_streams(context: Context) -> None:
    context.deps = deps("llm_stub_answer.json")


@when("cytaty nie przeszły jeszcze weryfikacji")
def citations_not_verified(context: Context) -> None:
    run(context, DEFAULT_TEXT)
    context.before_verified = [
        status
        for status in context.runtime.published
        if any(
            step.code == "verify_citations" and step.status != "done"
            for step in status.steps
        )
    ]


@then("wersja wstępna nie zawiera werdyktu")
def draft_has_no_verdict(context: Context) -> None:
    assert context.before_verified
    assert all(status.result is None for status in context.before_verified)
    assert context.runtime.published[-1].result is not None
