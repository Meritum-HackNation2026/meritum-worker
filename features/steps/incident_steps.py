"""Steps of the incident scenarios in features/evidence.feature.

Keyed embeddings and the in-memory incident copy, no network and no model.
"""

import asyncio
import dataclasses
from datetime import UTC, date, datetime

from behave import given, then, when
from behave.runner import Context
from tests.checks.incident_support import (
    CLAIM_PL,
    FACT,
    OFF_TOPIC,
    ON_TOPIC,
    case,
    checked,
    embeddings,
)
from tests.evidence.incident_support import MATCHES, answered, supported
from tests.evidence.support import deps

from meritum_worker.checks.steps import match_incidents
from meritum_worker.corpus import build_euvsdisinfo_copy
from meritum_worker.evidence import (
    IncidentCandidate,
    IncidentProbe,
    RecordedLlm,
    match_incident,
)

DISPATCH_DAY = date(2026, 11, 20)


@given("w lokalnej kopii EUvsDisinfo przypadek opisany po angielsku")
def english_case(context: Context) -> None:
    context.entries = [case()]
    context.state = checked()


@given("sprawdzany link do domeny z linksToDisinformation i wpis o temacie twierdzenia")
def flagged_domain(context: Context) -> None:
    context.entries = [case(title="A different story", domains=("fake.example",))]
    context.state = checked("https://www.fake.example/a")


@when("obywatel sprawdza podobne twierdzenie po polsku")
def run_match(context: Context) -> None:
    copy = build_euvsdisinfo_copy()
    asyncio.run(copy.upsert(context.entries))
    ports = dataclasses.replace(
        deps(RecordedLlm({})), incidents=copy, embeddings=embeddings()
    )
    context.state = asyncio.run(match_incidents(context.state, ports))
    context.match = context.state.incidents.get(CLAIM_PL)


@then(
    'wynik zawiera IncidentMatch z database "euvsdisinfo", matched_on "content",'
    " tytułem, datą i linkiem do opisu przypadku"
)
def content_match(context: Context) -> None:
    match = context.match
    assert match is not None
    assert (match.database, match.matched_on) == ("euvsdisinfo", "content")
    assert match.title
    assert str(match.url).startswith("https://euvsdisinfo.eu/report/")


@then('tekst fact jest dowodem wtórnym wydawcy "{publisher}"')
def fact_is_secondary(context: Context, publisher: str) -> None:
    [fact] = context.state.evidence
    assert fact.text == FACT
    assert fact.source.tier == "secondary"
    assert fact.source.publisher_id == "eeas-euvsdisinfo"
    assert publisher.startswith("EUvsDisinfo")


@then('wynik ma IncidentMatch z matched_on "domain"')
def domain_match(context: Context) -> None:
    assert context.match is not None
    assert context.match.matched_on == "domain"


@given("to samo sprawdzenie z dopasowaniem i ostrzeżeniem o domenie oraz bez nich")
def with_and_without(context: Context) -> None:
    context.matches = MATCHES


@when("system liczy werdykt")
def count_verdicts(context: Context) -> None:
    plain = [answered(supported())]
    states = [*plain, *(answered(supported(), m) for m in context.matches)]
    context.verdicts = [
        s.result.claims[0].model_dump(exclude={"incident"})
        for s in states
        if s.result is not None
    ]


@then("werdykt jest identyczny w obu przypadkach")
def same_verdict(context: Context) -> None:
    first, *others = context.verdicts
    assert len(others) == len(MATCHES)
    assert all(other == first for other in others)


def _rated(title: tuple[float, ...]) -> IncidentCandidate:
    return IncidentCandidate(
        database="fact_check",
        incident_id="demagog-pap-1",
        title="Depesza PAP o cenach prądu",
        date=datetime(2026, 11, 20, tzinfo=UTC),
        url="https://demagog.org.pl/wypowiedzi/depesza-pap",
        description_vector=ON_TOPIC,
        title_vector=title,
    )


@given(
    "wpis z pap.pl z tym samym tytułem, tematem i datą depeszy co publikacja"
    " oceniona przez Demagoga"
)
def same_dispatch(context: Context) -> None:
    context.candidates = [_rated(ON_TOPIC)]


@given("wpis z pap.pl o podobnym temacie, ale o innej depeszy")
def other_dispatch(context: Context) -> None:
    context.candidates = [_rated(OFF_TOPIC)]


@when("system dopasowuje wpis do znanych incydentów")
def match_post(context: Context) -> None:
    probe = IncidentProbe(vector=ON_TOPIC, on=DISPATCH_DAY, domain="pap.pl")
    context.match = match_incident(probe, context.candidates)


@then(
    'IncidentMatch ma matched_on "content" i podstawę dopasowania: tytuł, temat i data'
)
def content_basis(context: Context) -> None:
    assert context.match is not None
    assert context.match.matched_on == "content"
    assert {"title", "topic", "date"} <= set(context.match.match_basis)


@then("wynik nie ma dopasowania treści")
def no_content_match(context: Context) -> None:
    assert context.match is None or context.match.matched_on != "content"
