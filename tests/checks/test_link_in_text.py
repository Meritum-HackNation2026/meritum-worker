import asyncio
from collections.abc import Callable
from dataclasses import replace

import pytest
from meritum_core.checks import CheckRequest
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchPurpose,
    PaywallError,
    RobotsDisallowedError,
)
from meritum_core.jobs.contracts import CheckInput
from tests.llm_fakes import RecordingLlm

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    ClaimExtraction,
    ExtractedClaim,
    FakePageFetcher,
    InlineCheckRuntime,
    run_check,
)
from meritum_worker.checks.prompts import (
    LINKED_PAGE_INSTRUCTIONS,
    QUESTION_AND_PAGE_INSTRUCTIONS,
    UNREAD_LINK_INSTRUCTIONS,
)
from meritum_worker.checks.steps import extract_claims, fetch_url, receive

LINK = "https://example.com/rosyjskie-rakiety-spadly-w-polsce"
QUESTION = f"Czy ten artykuł mówi prawdę {LINK}"
PAGE_TEXT = "Dwie rosyjskie rakiety spadły w Polsce podczas ataku na Ukrainę."
FACT = ExtractedClaim(
    claim="Dwie rosyjskie rakiety spadły w Polsce",
    kind="fact",
    explanation="Zdarzenie, które źródła mogą potwierdzić.",
    fact_check_phrases=["rosyjskie rakiety Polska"],
)

type MakeJob = Callable[..., CheckInput]
type MakeDeps = Callable[..., CheckDeps]


def _state(make_job: MakeJob, **request: str) -> CheckState:
    job = make_job().model_copy(
        update={"request": CheckRequest.model_validate({"channel": "web", **request})}
    )
    return CheckState(check_id="check-1", job=job)


def _received(make_job: MakeJob, make_deps: MakeDeps, **request: str) -> CheckState:
    return asyncio.run(receive(_state(make_job, **request), make_deps()))


def _page() -> FetchedPage:
    return FetchedPage(url=LINK, content_type="text/html", untrusted_text=PAGE_TEXT)


@pytest.mark.parametrize(
    "text",
    [QUESTION, f"Co jest nieprawdą w tym tekście? ({LINK}).", f"{LINK} to prawda?"],
)
def test_receive_lifts_a_link_out_of_the_text_and_keeps_the_question(
    make_job: MakeJob, make_deps: MakeDeps, text: str
) -> None:
    request = _received(make_job, make_deps, text=text).job.request
    assert str(request.url) == LINK
    assert request.text == text


def test_receive_reads_a_text_that_is_only_a_link_as_a_link(
    make_job: MakeJob, make_deps: MakeDeps
) -> None:
    request = _received(make_job, make_deps, text=f"  {LINK} ").job.request
    assert (str(request.url), request.text) == (LINK, None)


def test_receive_leaves_a_text_without_a_link_and_a_given_link_alone(
    make_job: MakeJob, make_deps: MakeDeps
) -> None:
    plain = _state(make_job, text="Płaca minimalna wynosi 4806 zł")
    assert asyncio.run(receive(plain, make_deps())) == plain
    other = "https://example.org/inny"
    given = _received(make_job, make_deps, text=QUESTION, url=other)
    assert str(given.job.request.url) == other


def test_fetch_url_reads_the_page_next_to_a_question(
    make_job: MakeJob, make_deps: MakeDeps
) -> None:
    pages = FakePageFetcher(_page())
    state = _state(make_job, text=QUESTION, url=LINK)
    out = asyncio.run(fetch_url(state, make_deps(pages=pages)))
    assert pages.calls == [(LINK, FetchPurpose.USER_LINK)]
    assert out.page_text == PAGE_TEXT
    assert out.question == QUESTION


@pytest.mark.parametrize("error", [PaywallError(), RobotsDisallowedError()], ids=str)
def test_fetch_url_says_the_page_was_not_read_and_lets_the_check_go_on(
    make_job: MakeJob, make_deps: MakeDeps, error: PaywallError
) -> None:
    state = _state(make_job, text=QUESTION, url=LINK)
    out = asyncio.run(fetch_url(state, make_deps(pages=FakePageFetcher(error))))
    assert out.result is None
    assert out.failed_steps == ["fetch_url"]
    (note,) = out.limitations
    assert "example.com" in note
    assert "Nie udało się otworzyć" in note


def _extract(
    state: CheckState, deps: CheckDeps, *claims: ExtractedClaim
) -> tuple[CheckState, str]:
    llm = RecordingLlm(ClaimExtraction(out_of_scope=False, claims=[*claims]))
    out = asyncio.run(extract_claims(state, replace(deps, llm=llm)))
    (prompt,) = llm.prompts
    assert all(item not in prompt.instructions for item in prompt.data)
    return out, prompt.instructions + "\x00" + "\x00".join(prompt.data)


def test_extraction_gets_the_question_and_the_page_as_separate_data(
    make_job: MakeJob, make_deps: MakeDeps
) -> None:
    state = _state(make_job, text=QUESTION, url=LINK)
    state = state.model_copy(update={"page_text": PAGE_TEXT})
    out, prompt = _extract(state, make_deps(), FACT)
    assert prompt.endswith(f"\x00{QUESTION}\x00{PAGE_TEXT}")
    assert LINKED_PAGE_INSTRUCTIONS in prompt
    assert QUESTION_AND_PAGE_INSTRUCTIONS in prompt
    assert [claim.claim for claim in out.claims] == [FACT.claim]


def test_extraction_of_a_bare_link_asks_for_the_main_claims_of_the_page(
    make_job: MakeJob, make_deps: MakeDeps
) -> None:
    state = _state(make_job, url=LINK).model_copy(update={"page_text": PAGE_TEXT})
    _, prompt = _extract(state, make_deps(), FACT)
    assert prompt.endswith(f"\x00{PAGE_TEXT}")
    assert LINKED_PAGE_INSTRUCTIONS in prompt
    assert QUESTION_AND_PAGE_INSTRUCTIONS not in prompt


def test_unread_page_is_checked_by_its_address_and_searched_in_fact_checks(
    make_job: MakeJob, make_deps: MakeDeps
) -> None:
    out, prompt = _extract(_state(make_job, url=LINK), make_deps(), FACT)
    assert prompt.endswith(f"\x00{LINK}")
    assert UNREAD_LINK_INSTRUCTIONS in prompt
    assert out.claims[0].fact_check_phrases == [LINK, "rosyjskie rakiety Polska"]


def test_unread_page_without_a_claim_is_url_unavailable_not_a_clarification(
    make_job: MakeJob, make_deps: MakeDeps
) -> None:
    out, _ = _extract(_state(make_job, text=QUESTION, url=LINK), make_deps())
    assert out.result is not None
    assert out.result.status == "technical_failure"
    assert out.result.failure_code == "url_unavailable"


@pytest.mark.parametrize(
    ("request_field", "state_field"),
    [("image_id", "image_text"), ("audio_id", "transcript")],
)
def test_image_and_voice_reach_the_same_claim_extraction(
    make_job: MakeJob, make_deps: MakeDeps, request_field: str, state_field: str
) -> None:
    state = _state(make_job, **{request_field: "blob-1"})
    out, prompt = _extract(
        state.model_copy(update={state_field: PAGE_TEXT}), make_deps(), FACT
    )
    assert prompt.endswith(f"\x00{PAGE_TEXT}")
    assert LINKED_PAGE_INSTRUCTIONS not in prompt
    assert [claim.claim for claim in out.claims] == [FACT.claim]


def test_check_of_a_question_with_a_link_reads_the_article(
    make_job: MakeJob, make_deps: MakeDeps
) -> None:
    pages = FakePageFetcher(_page())
    job = _state(make_job, text=QUESTION).job
    runtime = InlineCheckRuntime()
    deps = make_deps(pages=pages)
    output = asyncio.run(run_check(job.model_dump(mode="json"), "c-1", deps, runtime))
    statuses = {s.code: s.status for s in runtime.published[-1].steps}
    assert pages.calls == [(LINK, FetchPurpose.USER_LINK)]
    assert statuses["fetch_url"] == "done"
    assert output.result.status == "done"
