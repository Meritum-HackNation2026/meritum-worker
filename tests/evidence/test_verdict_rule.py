import asyncio
from datetime import UTC, date, datetime

from meritum_core.checks.contracts import Citation, ClaimResult
from tests.evidence.support import deps, state_with

from meritum_worker.checks import AnswerDraft, CheckState
from meritum_worker.checks.steps import assess_evidence, verify_citations, write_answer
from meritum_worker.evidence import (
    ClaimExplanation,
    RecordedLlm,
    StanceJudgement,
    document,
    judge,
)

SUPPORT = "Płaca minimalna od 1 stycznia wynosi 4806 zł brutto miesięcznie."
REFUTE = "Płaca minimalna od 1 stycznia nie wynosi 4806 zł, lecz 4666 zł brutto."
EXPLAINED = ClaimExplanation(
    explanation="Fragmenty źródeł opisują kwotę płacy minimalnej.",
    unresolved="Nie ustalono kwoty; rozstrzygnąłby ją komunikat GUS.",
)


def _run(state: CheckState, llm: RecordedLlm) -> ClaimResult:
    ports = deps(llm)
    for step in (assess_evidence, verify_citations, write_answer):
        state = asyncio.run(step(state, ports))
    assert state.result is not None
    assert state.result.status == "done", state.result.message
    return state.result.claims[0]


def _llm(stances: dict[str, StanceJudgement]) -> RecordedLlm:
    draft = AnswerDraft(claims=[EXPLAINED], limitations=["Sprawdzono tylko korpus."])
    return RecordedLlm(stances, draft)


def _says(text: str, stance: str, fragment: str | None = None) -> StanceJudgement:
    return StanceJudgement.model_validate(
        {"relevant": True, "fragment": fragment or text, "stance": stance}
    )


def test_fragment_not_in_the_source_is_dropped_and_the_claim_is_insufficient() -> None:
    source = document("gus-1", SUPPORT)
    llm = _llm({SUPPORT: _says(SUPPORT, "supports", "Płaca wynosi 5000 zł od dziś.")})

    claim = _run(state_with("tekst", [source]), llm)

    assert claim.verdict == "insufficient_evidence"
    assert claim.citations == []
    assert claim.strength is None
    assert claim.unresolved == EXPLAINED.unresolved


def test_supporting_fragment_confirms_with_strength_and_metadata_from_database() -> (
    None
):
    source = document("gus-1", SUPPORT, published_at=datetime(2025, 12, 1, tzinfo=UTC))
    llm = _llm({SUPPORT: _says(SUPPORT, "supports")})

    claim = _run(state_with("tekst", [source]), llm)

    assert claim.verdict == "confirmed"
    assert claim.strength is not None
    assert claim.strength.premises.primary_sources == 1
    assert claim.citations[0].source == source.source
    assert claim.explanation == EXPLAINED.explanation
    assert "needs_second_publisher" in claim.would_change_verdict


def test_estimate_and_budget_item_as_context_do_not_conflict() -> None:
    # Scenario C: 650 mln zł is a budget item for 2023, 700 mln zł an estimate.
    budget = "W 2023 r. wydatki na transport zbiorowy wyniosły 650 mln zł."
    said = "Prezydent powiedział, że miasto wydaje około 700 mln zł na komunikację."
    sources = [
        document("demagog-1", budget, publisher_id="demagog", tier="secondary"),
        document("um-1", said, publisher_id="um-wroclaw", domain="wroclaw.pl"),
    ]
    llm = _llm({budget: _says(budget, "context"), said: _says(said, "supports")})
    state = state_with("Czy Wrocław wydaje około 700 mln zł?", sources)

    claim = _run(state, llm)

    assert claim.verdict == "confirmed"
    assert claim.strength is not None
    assert claim.strength.premises.agreement == "consistent"


def test_conflicting_sources_give_insufficient_evidence_with_both_sides() -> None:
    sources = [
        document("gus-1", SUPPORT),
        document("mrpips-1", REFUTE, publisher_id="mrpips", domain="gov.pl"),
    ]
    llm = _llm({SUPPORT: _says(SUPPORT, "supports"), REFUTE: _says(REFUTE, "refutes")})

    claim = _run(state_with("tekst", sources), llm)

    assert claim.verdict == "insufficient_evidence"
    assert claim.strength is None
    assert {c.stance for c in claim.citations} == {"supports", "refutes"}


def test_older_support_superseded_by_newer_refutation_is_false_and_outdated() -> None:
    sources = [
        document("gus-old", SUPPORT, published_at=datetime(2025, 5, 1, tzinfo=UTC)),
        document("gus-new", REFUTE, published_at=datetime(2026, 3, 1, tzinfo=UTC)),
    ]
    llm = _llm({SUPPORT: _says(SUPPORT, "supports"), REFUTE: _says(REFUTE, "refutes")})
    state = state_with("tekst", sources, claim_date=date(2026, 11, 1))

    claim = _run(state, llm)

    validity = {c.source.id: c.validity for c in claim.citations}
    assert validity["gus-old"] == "superseded"
    assert claim.verdict == "false"
    assert claim.technique == "outdated"
    assert claim.strength is not None
    assert claim.strength.premises.agreement == "consistent"


def test_stale_supporting_evidence_is_archival_and_weak() -> None:
    old = datetime(2020, 1, 1, tzinfo=UTC)
    citation = Citation(
        source=document("gus-1", SUPPORT, published_at=old).source,
        fragment=SUPPORT,
        stance="supports",
    )

    judged = judge([citation], catalog={}, claim_date=date(2026, 1, 1))

    assert judged.verdict == "confirmed"
    assert judged.archival
    assert judged.strength is not None
    assert judged.strength.level == "weak"


def test_context_alone_settles_nothing_and_shows_no_citation() -> None:
    citation = Citation(
        source=document("gus-1", SUPPORT).source, fragment=SUPPORT, stance="context"
    )

    judged = judge([citation], catalog={}, claim_date=date(2026, 1, 1))

    assert (judged.verdict, judged.strength, judged.citations) == (
        "insufficient_evidence",
        None,
        [],
    )
