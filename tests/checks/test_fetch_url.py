import asyncio
from collections.abc import Callable

import pytest
from meritum_core.checks import CheckRequest
from meritum_core.corpus.fetching import (
    BlockedAddressError,
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    JavaScriptRequiredError,
    LoginWallError,
    PageFetchError,
    PaywallError,
)
from meritum_core.jobs.contracts import CheckInput

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    FakePageFetcher,
    InlineCheckRuntime,
    run_check,
)
from meritum_worker.checks.steps import fetch_url

LINK = "https://example.com/artykul"
PAGE_TEXT = "Inflacja w październiku wyniosła 2,8%. Kontakt: 600 700 800."


def _url_state(make_job: Callable[..., CheckInput]) -> CheckState:
    job = make_job().model_copy(
        update={"request": CheckRequest(channel="web", url=LINK)}
    )
    return CheckState(check_id="check-1", job=job)


def _page(text: str = PAGE_TEXT) -> FetchedPage:
    return FetchedPage(url=LINK, content_type="text/html", untrusted_text=text)


def test_fetch_url_reads_the_link_as_a_user_link_and_masks_the_page_text(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    pages = FakePageFetcher(_page())
    out = asyncio.run(fetch_url(_url_state(make_job), make_deps(pages=pages)))
    assert pages.calls == [(LINK, FetchPurpose.USER_LINK)]
    assert out.result is None
    assert out.question.startswith("Inflacja w październiku wyniosła 2,8%.")
    assert "600 700 800" not in out.question


def test_fetch_url_cuts_a_long_page_to_the_length_of_a_pasted_text(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    pages = FakePageFetcher(_page("a" * 9000))
    out = asyncio.run(fetch_url(_url_state(make_job), make_deps(pages=pages)))
    assert len(out.question) == 4000


@pytest.mark.parametrize(
    "error",
    [
        BlockedAddressError(FetchFailureReason.BLOCKED_ADDRESS),
        BlockedAddressError(FetchFailureReason.REDIRECT_BLOCKED),
        LoginWallError(FetchFailureReason.LOGIN_WALL),
        PaywallError(),
        JavaScriptRequiredError(),
        PageFetchError(FetchFailureReason.UNREACHABLE),
        PageFetchError(FetchFailureReason.TIMEOUT),
        PageFetchError(FetchFailureReason.HTTP_ERROR),
        PageFetchError(FetchFailureReason.UNSUPPORTED_URL),
        PageFetchError(FetchFailureReason.TOO_MANY_REDIRECTS),
        PageFetchError(FetchFailureReason.UNSUPPORTED_CONTENT),
        PageFetchError(FetchFailureReason.TOO_LARGE),
    ],
    ids=str,
)
def test_fetch_url_turns_every_fetch_failure_into_url_unavailable(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    error: PageFetchError,
) -> None:
    pages = FakePageFetcher(error)
    out = asyncio.run(fetch_url(_url_state(make_job), make_deps(pages=pages)))
    assert out.result is not None
    assert out.result.status == "technical_failure"
    assert out.result.failure_code == "url_unavailable"
    assert out.result.message == "status_hint.technical_failure_url"
    assert out.result.claims == []


def test_fetch_url_skips_a_text_without_a_link(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    pages = FakePageFetcher(_page())
    state = CheckState(check_id="check-1", job=make_job())
    out = asyncio.run(fetch_url(state, make_deps(pages=pages)))
    assert pages.calls == []
    assert out.skipped_steps == ["fetch_url"]
    assert out.question == state.question


def _statuses(job: CheckInput, deps: CheckDeps) -> dict[str, str]:
    runtime = InlineCheckRuntime()
    asyncio.run(run_check(job.model_dump(mode="json"), "check-1", deps, runtime))
    return {step.code: step.status for step in runtime.published[-1].steps}


def test_check_of_a_text_shows_fetch_url_as_skipped(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    statuses = _statuses(make_job(), make_deps())
    assert statuses.pop("fetch_url") == "skipped"
    assert set(statuses.values()) == {"done"}


def test_check_of_an_unreachable_link_fails_at_fetch_url_without_a_verdict(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    pages = FakePageFetcher(LoginWallError(FetchFailureReason.LOGIN_WALL))
    deps = make_deps(pages=pages)
    job = _url_state(make_job).job
    runtime = InlineCheckRuntime()
    output = asyncio.run(run_check(job.model_dump(mode="json"), "c-1", deps, runtime))
    failed = [s.code for s in runtime.published[-1].steps if s.status == "failed"]
    assert failed == ["fetch_url"]
    assert output.result.failure_code == "url_unavailable"
    assert output.result.claims == []


def test_fetch_url_keeps_pasted_text_and_skips_the_link_next_to_it(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    pages = FakePageFetcher(LoginWallError(FetchFailureReason.LOGIN_WALL))
    request = CheckRequest(
        channel="web", text="Płaca minimalna wynosi 4806 zł", url=LINK
    )
    job = make_job().model_copy(update={"request": request})
    out = asyncio.run(
        fetch_url(CheckState(check_id="c-1", job=job), make_deps(pages=pages))
    )
    assert pages.calls == []
    assert out.result is None
    assert out.skipped_steps == ["fetch_url"]
    assert out.question == "Płaca minimalna wynosi 4806 zł"


def test_fetch_url_reads_the_link_when_the_text_next_to_it_is_only_spaces(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    pages = FakePageFetcher(_page())
    request = CheckRequest(channel="web", text="   ", url=LINK)
    job = make_job().model_copy(update={"request": request})
    state = CheckState(check_id="c-1", job=job)
    out = asyncio.run(fetch_url(state, make_deps(pages=pages)))
    assert pages.calls == [(LINK, FetchPurpose.USER_LINK)]
    assert out.question.startswith("Inflacja w październiku wyniosła 2,8%.")


def test_check_of_a_public_link_checks_the_page_text_and_ends_fetch_url_done(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    deps = make_deps(pages=FakePageFetcher(_page()))
    job = _url_state(make_job).job
    runtime = InlineCheckRuntime()
    output = asyncio.run(run_check(job.model_dump(mode="json"), "c-1", deps, runtime))
    statuses = {s.code: s.status for s in runtime.published[-1].steps}
    assert statuses["fetch_url"] == "done"
    assert output.result.status == "done"
    record = asyncio.run(deps.records.get("c-1"))
    assert record is not None
    assert record.question_masked.startswith("Inflacja w październiku wyniosła 2,8%.")


def test_fetch_url_treats_an_empty_page_as_unavailable(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    pages = FakePageFetcher(_page("  \n "))
    out = asyncio.run(fetch_url(_url_state(make_job), make_deps(pages=pages)))
    assert out.result is not None
    assert out.result.failure_code == "url_unavailable"
