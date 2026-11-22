"""Steps of features/evidence.feature: stance per citation, verdict from core rules.

Recorded model answers (RecordedLlm), in-process ports, no network.
"""

import asyncio
from datetime import UTC, date, datetime

from behave import given, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.evidence import SourceDocument
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate

from meritum_worker.checks import (
    AnswerDraft,
    CheckDeps,
    CheckState,
    ExtractedClaim,
    FakePageFetcher,
    audio_ports,
    corpus_ports,
    web_ports,
)
from meritum_worker.checks.steps import assess_evidence, verify_citations, write_answer
from meritum_worker.evidence import (
    ClaimExplanation,
    RecordedLlm,
    StanceJudgement,
    document,
)

SUPPORT = "Płaca minimalna od 1 stycznia wynosi 4806 zł brutto miesięcznie."
REFUTE = "Płaca minimalna od 1 stycznia nie wynosi 4806 zł, lecz 4666 zł brutto."
NET_ONLY = "Od 1 stycznia 2026 r. płaca minimalna wynosi 4806 zł miesięcznie."
BUDGET = "W 2023 r. wydatki na transport zbiorowy wyniosły 650 mln zł."
SAID = "Prezydent powiedział, że miasto wydaje około 700 mln zł na komunikację."
STRIKE = "Związki zapowiedziały strajk generalny we Włoszech na 20 listopada 2026 r."
NO_CHANGE = "Brak wyniku w bazie nie oznacza, że zmiany nie było."


def _given(  # ruff: ignore[too-many-arguments]  # each scenario sets its own pair
    context: Context,
    claim: str,
    sources: list[SourceDocument],
    stances: dict[str, StanceJudgement],
    written: ClaimExplanation,
    *,
    claim_date: date = date(2026, 1, 1),
) -> None:
    job = CheckInput(
        request=CheckRequest(channel="web", text=claim),
        received_at=datetime(2026, 11, 22, 12, 0, tzinfo=UTC),
        session_id="session-behave-1",
    )
    fact = ExtractedClaim(
        claim=claim,
        kind="fact",
        explanation="Twierdzenie o faktach, które da się sprawdzić.",
        claim_date=claim_date,
        claim_date_source="text",
    )
    context.state = CheckState(
        check_id="check-behave-1", job=job, claims=[fact], evidence=sources
    )
    draft = AnswerDraft(claims=[written], limitations=["Sprawdzono tylko korpus."])
    context.llm = RecordedLlm(stances, draft)


def _says(fragment: str, stance: str) -> StanceJudgement:
    return StanceJudgement.model_validate(
        {"relevant": True, "fragment": fragment, "stance": stance}
    )


def _insufficient(unresolved: str) -> ClaimExplanation:
    return ClaimExplanation(
        explanation="Źródła nie rozstrzygają twierdzenia.", unresolved=unresolved
    )


@given(
    "źródło z kwotą 4806 zł, które nie mówi, że jest to kwota brutto, i twierdzenie"
    " o 4806 zł brutto"
)
def partial_support(context: Context) -> None:
    stance = StanceJudgement.model_validate(
        {
            "relevant": True,
            "fragment": NET_ONLY,
            "stance": "supports",
            "missing": "brutto",
        }
    )
    _given(
        context,
        "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł brutto",
        [document("gus-1", NET_ONLY)],
        {NET_ONLY: stance},
        _insufficient("Nie ustalono, czy kwota jest brutto; rozstrzygnęłoby to GUS."),
    )


@given("model wskazał jedyny fragment, którego nie ma dosłownie w tekście źródła")
def fragment_not_in_source(context: Context) -> None:
    stance = _says("Płaca wynosi 5000 zł od dziś.", "supports")
    unresolved = "Nie ustalono kwoty; rozstrzygnąłby ją komunikat GUS."
    _given(
        context,
        "Płaca minimalna wynosi 4806 zł",
        [document("gus-1", SUPPORT)],
        {SUPPORT: stance},
        _insufficient(unresolved),
    )


@given(
    "przesłanka, że 650 mln zł to wydatki na transport zbiorowy w 2023 r., a 700 mln"
    " zł to przybliżenie z wypowiedzi polityka"
)
def estimate_and_budget(context: Context) -> None:
    sources = [
        document("demagog-1", BUDGET, publisher_id="demagog", tier="secondary"),
        document("um-1", SAID, publisher_id="um-wroclaw", domain="wroclaw.pl"),
    ]
    written = ClaimExplanation(
        explanation="700 mln zł to szacunek z wypowiedzi, a 650 mln zł to"
        " konkretna pozycja budżetu za 2023 r."
    )
    stances = {BUDGET: _says(BUDGET, "context"), SAID: _says(SAID, "supports")}
    _given(
        context,
        "Wrocław wydaje na komunikację około 700 mln zł",
        sources,
        stances,
        written,
    )


@given(
    "pytanie o bilety w Pcimiu i brak dowodów w korpusie, sieci i indeksie"
    " fact-checkerów"
)
def no_evidence(context: Context) -> None:
    unresolved = (
        "Nie ustalono, czy bilety są tylko w aplikacji; rozstrzygnąłby to komunikat"
        " lokalnego organizatora transportu albo regulamin sprzedaży biletów."
        f" {NO_CHANGE}"
    )
    claim = "Od wczoraj w Pcimiu bilety autobusowe można kupić tylko przez aplikację"
    _given(context, claim, [], {}, _insufficient(unresolved))


@given("strona o strajku zapowiedzianym na 20 listopada 2026 r.")
def announced_strike(context: Context) -> None:
    page = document("odyseusz-1", STRIKE, publisher_id="msz", domain="gov.pl")
    unresolved = "Nie wiadomo, czy strajk się odbył; rozstrzygnąłby komunikat po nim."
    _given(
        context,
        "We Włoszech ostatnio odbył się strajk generalny",
        [page],
        {STRIKE: _says(STRIKE, "context")},
        _insufficient(unresolved),
    )


@given(
    "ważne w dacie twierdzenia cytaty wspierające i obalające od różnych publisher_id"
)
def conflicting(context: Context) -> None:
    sources = [
        document("gus-1", SUPPORT),
        document("mrpips-1", REFUTE, publisher_id="mrpips", domain="gov.pl"),
    ]
    stances = {SUPPORT: _says(SUPPORT, "supports"), REFUTE: _says(REFUTE, "refutes")}
    unresolved = "Źródła podają różne kwoty; rozstrzygnęłoby rozporządzenie."
    _given(
        context,
        "Płaca minimalna wynosi 4806 zł",
        sources,
        stances,
        _insufficient(unresolved),
    )


@given(
    "twierdzenie z claim_date 2026-11-01 i starszy dowód wspierający z 2025 roku oraz"
    " nowszy urzędowy dowód obalający z 2026-03-01 od tego samego wydawcy"
)
def superseded(context: Context) -> None:
    sources = [
        document("gus-old", SUPPORT, published_at=datetime(2025, 5, 1, tzinfo=UTC)),
        document("gus-new", REFUTE, published_at=datetime(2026, 3, 1, tzinfo=UTC)),
    ]
    stances = {SUPPORT: _says(SUPPORT, "supports"), REFUTE: _says(REFUTE, "refutes")}
    written = ClaimExplanation(explanation="Nowszy komunikat GUS zastąpił starszy.")
    claim = "Płaca minimalna wynosi 4806 zł"
    _given(context, claim, sources, stances, written, claim_date=date(2026, 11, 1))


@when("system weryfikuje cytaty")
@when("system ustala wymowę i werdykt")
@when("system pisze odpowiedź")
@when("system ustala werdykt")
@when("system ustala ważność dowodów")
def run_evidence_steps(context: Context) -> None:
    ports = CheckDeps(
        llm=context.llm,
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **corpus_ports(),
        **web_ports(),
    )
    state = context.state
    for step in (assess_evidence, verify_citations, write_answer):
        state = asyncio.run(step(state, ports))
    context.state = state
    assert state.result is not None
    assert state.result.status == "done", state.result.message
    context.claim = state.result.claims[0]
