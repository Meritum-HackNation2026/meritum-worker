import asyncio
import dataclasses
from pathlib import Path

import httpx2
import pytest
from meritum_core.corpus.catalog import load_catalog
from tests.evidence.support import CLAIM, deps, state_with

from meritum_worker.checks import AnswerDraft, CheckDeps, CheckState
from meritum_worker.checks.fact_check_constants import FACT_CHECK_UNAVAILABLE_NOTE
from meritum_worker.checks.steps import (
    assess_evidence,
    search_fact_checks,
    write_answer,
)
from meritum_worker.corpus import FactCheckUnavailableError, FakeFactCheck
from meritum_worker.corpus.adapters import GoogleFactCheck
from meritum_worker.evidence import ClaimExplanation, RecordedLlm, ReviewMatch

FIXTURES = Path(__file__).resolve().parents[2] / "features" / "fixtures"
EXPLAINED = ClaimExplanation(
    explanation="Ocena fact-checkera prowadzi do tego werdyktu.",
    unresolved="Brak innych źródeł rozstrzygających twierdzenie.",
)


def _api(fixture: str) -> GoogleFactCheck:
    body = (FIXTURES / fixture).read_bytes()
    client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(
            lambda _: httpx2.Response(
                200, content=body, headers={"Cache-Control": "max-age=3600"}
            )
        )
    )
    return GoogleFactCheck("k-recorded", client)


def _run(*, same_claim: bool, api: object, repeat_search: bool = False) -> CheckState:
    llm = RecordedLlm(
        {},
        ReviewMatch(same_claim=same_claim),
        AnswerDraft(claims=[EXPLAINED], limitations=["Sprawdzono indeks ocen."]),
    )
    ports: CheckDeps = dataclasses.replace(
        deps(llm), catalog=load_catalog(), fact_check=api
    )

    async def go() -> CheckState:
        state = await search_fact_checks(state_with(CLAIM, []), ports)
        if repeat_search:
            state = await search_fact_checks(state, ports)
        state = await assess_evidence(state, ports)
        return await write_answer(state, ports)

    return asyncio.run(go())


def test_a_demagog_rating_of_the_same_claim_is_a_premise_with_a_link() -> None:
    done = _run(same_claim=True, api=_api("fact_check_demagog.json"))
    assert done.result is not None
    [claim] = done.result.claims
    [premise] = claim.claim_review_premises
    assert (premise.publisher_id, premise.rating) == ("demagog", "Fałsz")
    assert str(premise.url).startswith("https://demagog.org.pl/")
    assert claim.verdict == "false"
    assert claim.strength is not None
    assert claim.citations == []  # no page fragment of Demagog
    assert [r.publisher for r in claim.claim_reviews] == []


def test_a_rating_of_another_claim_stays_context() -> None:
    done = _run(same_claim=False, api=_api("fact_check_demagog.json"))
    assert done.result is not None
    [claim] = done.result.claims
    assert claim.claim_review_premises == []
    assert claim.verdict == "insufficient_evidence"
    assert [r.rating for r in claim.claim_reviews] == ["Fałsz"]


@pytest.mark.parametrize("same_claim", [True, False])
def test_repeated_review_is_written_once(*, same_claim: bool) -> None:
    done = _run(
        same_claim=same_claim,
        api=_api("fact_check_demagog.json"),
        repeat_search=True,
    )
    assert done.result is not None
    [claim] = done.result.claims
    [review] = [*claim.claim_review_premises, *claim.claim_reviews]
    assert (review.publisher, review.rating) == ("Stowarzyszenie Demagog", "Fałsz")


def test_an_empty_answer_is_no_rating_and_no_failure() -> None:
    done = _run(same_claim=True, api=_api("fact_check_empty.json"))
    assert done.failed_steps == []
    assert done.result is not None
    assert "fact_check_unavailable" not in done.result.limitation_codes


@pytest.mark.parametrize("status", [403, 429, 500])
def test_a_failed_api_ends_the_step_failed_and_the_check_goes_on(status: int) -> None:
    client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda _: httpx2.Response(status))
    )
    done = _run(same_claim=True, api=GoogleFactCheck("k", client))
    assert done.failed_steps == ["search_fact_checks"]
    assert done.result is not None
    assert done.result.status == "done"
    assert "fact_check_unavailable" in done.result.limitation_codes
    assert FACT_CHECK_UNAVAILABLE_NOTE in done.result.limitations
    assert "nie znaczy" in FACT_CHECK_UNAVAILABLE_NOTE  # never "there is none"


def test_no_key_fails_the_same_way() -> None:
    done = _run(
        same_claim=True,
        api=FakeFactCheck(failure=FactCheckUnavailableError("no_api_key")),
    )
    assert done.failed_steps == ["search_fact_checks"]
