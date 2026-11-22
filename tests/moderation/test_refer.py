from datetime import timedelta

from meritum_core.moderation import HighRiskTopic
from tests.moderation.conftest import NOW, Ask, Make, record, sync

from meritum_worker.moderation import InMemoryCheckResults, refer

DIESEL = "Czy od przyszłego tygodnia diesle nie będą mogły wjechać do centrum Pcimia?"
PARAPHRASE = "Czy Pcim wprowadza zakaz wjazdu diesli do centrum?"
CLOSE: dict[str, tuple[float, ...]] = {DIESEL: (1.0, 0.1), PARAPHRASE: (1.0, 0.2)}


@sync
async def test_a_single_unanswered_claim_is_only_recommended(
    make: Make, ask: Ask
) -> None:
    deps = make()
    found = await refer(ask("Czy woda w Pcimiu jest zdatna do picia?", "c1"), deps)
    assert (found.state, found.case_id) == ("recommended", None)
    assert await deps.cases.list_cases() == []


@sync
async def test_a_click_opens_a_case_with_a_number(make: Make, ask: Ask) -> None:
    deps = make()
    found = await refer(
        ask("Czy woda w Pcimiu jest zdatna do picia?", "c1", "recommended_clicked"),
        deps,
    )
    assert (found.state, found.case_id) == ("created", "#S-1")
    case = await deps.cases.get("#S-1")
    assert case is not None
    assert case.reasons == ["insufficient_evidence"]


@sync
async def test_a_paraphrase_from_another_check_joins_one_case(
    make: Make, ask: Ask
) -> None:
    deps = make(CLOSE)
    assert isinstance(deps.results, InMemoryCheckResults)
    deps.results.add("c1", NOW - timedelta(days=1), [(DIESEL, True)])
    await record(deps, "c1")
    await record(deps, "c2")
    found = await refer(ask(PARAPHRASE, "c2"), deps)
    assert found.state == "created"
    case = await deps.cases.get(found.case_id or "")
    assert case is not None
    assert case.reasons == ["repeated_unanswered"]
    assert case.check_ids == ["c2", "c1"]
    assert case.distinct_askers == 2


@sync
async def test_a_third_similar_claim_updates_the_open_case(
    make: Make, ask: Ask
) -> None:
    deps = make(CLOSE)
    assert isinstance(deps.results, InMemoryCheckResults)
    deps.results.add("c1", NOW - timedelta(days=1), [(DIESEL, True)])
    await record(deps, "c1")
    await record(deps, "c2")
    first = await refer(ask(PARAPHRASE, "c2"), deps)
    again = await refer(ask(DIESEL, "c3"), deps)
    assert (again.state, again.case_id) == ("updated", first.case_id)
    case = await deps.cases.get(again.case_id or "")
    assert case is not None
    assert case.similar_count == 3
    assert case.distinct_askers == 3


@sync
async def test_the_same_check_twice_does_not_add_an_asker(make: Make, ask: Ask) -> None:
    deps = make()
    await refer(
        ask("Czy woda w Pcimiu jest zdatna?", "c1", "recommended_clicked"), deps
    )
    again = await refer(
        ask("Czy woda w Pcimiu jest zdatna?", "c1", "recommended_clicked"), deps
    )
    case = await deps.cases.get(again.case_id or "")
    assert (again.state, case and case.distinct_askers) == ("updated", 1)


@sync
async def test_a_high_risk_topic_opens_a_case_by_embeddings(
    make: Make, ask: Ask, health: HighRiskTopic
) -> None:
    deps = make(
        {"Czy szczepionki są groźne?": (1.0, 0.0), "zdrowie: szczepion": (1.0, 0.1)}
    )
    await deps.topics.save_topic(health)
    found = await refer(ask("Czy szczepionki są groźne?", "c1"), deps)
    case = await deps.cases.get(found.case_id or "")
    assert case is not None
    assert case.reasons == ["high_risk"]
    assert (case.high_risk_topic, case.high_risk_classified_by) == (
        "zdrowie",
        "embeddings",
    )


@sync
async def test_keywords_classify_when_embeddings_do_not_match(
    make: Make, ask: Ask, health: HighRiskTopic
) -> None:
    deps = make(
        {"Czy szczepionki są groźne?": (1.0, 0.0), "zdrowie: szczepion": (0.0, 1.0)}
    )
    await deps.topics.save_topic(health)
    found = await refer(ask("Czy szczepionki są groźne?", "c1"), deps)
    case = await deps.cases.get(found.case_id or "")
    assert case is not None
    assert case.high_risk_classified_by == "keywords"


@sync
async def test_different_numbers_are_different_cases(make: Make, ask: Ask) -> None:
    deps = make({"inflacja wynosi 5%": (1.0, 0.0), "inflacja wynosi 15%": (1.0, 0.01)})
    first = await refer(ask("inflacja wynosi 5%", "c1", "recommended_clicked"), deps)
    other = await refer(ask("inflacja wynosi 15%", "c2", "recommended_clicked"), deps)
    assert (other.state, other.case_id) == ("created", "#S-2")
    assert first.case_id == "#S-1"


@sync
async def test_a_dispute_keeps_its_reason(make: Make, ask: Ask) -> None:
    deps = make()
    found = await refer(
        ask("Czy woda w Pcimiu jest zdatna?", "c1", "user_dispute"), deps
    )
    case = await deps.cases.get(found.case_id or "")
    assert case is not None
    assert case.reasons == ["user_dispute"]
