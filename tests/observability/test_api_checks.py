"""A case checked through the Meritum API, as on dev (worker#170)."""

import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx2

from meritum_worker.observability import GoldenCase
from meritum_worker.observability.adapters import ApiChecks
from meritum_worker.observability.constants import API_RETRIES

DONE = json.loads(
    (Path(__file__).parent / "fixtures" / "api_check_done.json").read_text("utf-8")
)
BASE = "https://meritum.example"
PENDING = {"check_id": DONE["check_id"], "steps": [], "result": None}


def _client(
    replies: Sequence[httpx2.Response | Exception],
    seen: list[httpx2.Request],
    poll_seconds: float = 0,
    timeout_seconds: float = 5,
    *,
    fresh: bool = False,
) -> ApiChecks:
    queue = list(replies)

    def reply(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        answer = queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    return ApiChecks(
        BASE,
        client,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
        fresh=fresh,
    )


def _accepted() -> httpx2.Response:
    return httpx2.Response(202, json={"check_id": DONE["check_id"]})


def test_case_is_posted_with_a_session_and_polled_until_the_result(
    case: Callable[..., GoldenCase],
) -> None:
    seen: list[httpx2.Request] = []
    replies = [_accepted(), httpx2.Response(200, json=PENDING)]
    checks = _client([*replies, httpx2.Response(200, json=DONE)], seen)
    run = asyncio.run(checks.check(case()))
    posted = json.loads(seen[0].content)
    assert seen[0].url == f"{BASE}/api/v1/checks"
    assert posted == {"channel": "web", "text": case().text}
    assert len(seen[0].headers["X-Meritum-Session"]) >= 8
    assert run.result.check_id == run.check_id == DONE["check_id"]
    assert run.result.claims[0].verdict == "insufficient_evidence"
    assert run.seconds >= 0


def test_rate_limited_post_waits_and_retries(
    case: Callable[..., GoldenCase],
) -> None:
    seen: list[httpx2.Request] = []
    limited = httpx2.Response(429, headers={"Retry-After": "0"})
    checks = _client([limited, _accepted(), httpx2.Response(200, json=DONE)], seen)
    run = asyncio.run(checks.check(case()))
    assert run.result.status == "done"
    assert [r.method for r in seen] == ["POST", "POST", "GET"]


def test_check_without_a_result_in_time_is_a_technical_failure(
    case: Callable[..., GoldenCase],
) -> None:
    seen: list[httpx2.Request] = []
    pending = [httpx2.Response(200, json=PENDING) for _ in range(50)]
    checks = _client([_accepted(), *pending], seen, 0.2, 0.5)
    run = asyncio.run(checks.check(case()))
    assert run.result.status == "technical_failure"
    assert run.result.check_id == DONE["check_id"]


def test_unavailable_api_waits_and_retries(case: Callable[..., GoldenCase]) -> None:
    seen: list[httpx2.Request] = []
    restarting = httpx2.Response(503, headers={"Retry-After": "0"})
    checks = _client([restarting, _accepted(), httpx2.Response(200, json=DONE)], seen)
    run = asyncio.run(checks.check(case()))
    assert run.result.status == "done"


def test_a_fresh_run_tags_the_text_so_the_result_cache_misses(
    case: Callable[..., GoldenCase],
) -> None:
    texts = []
    for _ in range(2):
        seen: list[httpx2.Request] = []
        replies = [_accepted(), httpx2.Response(200, json=DONE)]
        asyncio.run(_client(replies, seen, fresh=True).check(case()))
        texts.append(json.loads(seen[0].content)["text"])
    suffixes = [t.removeprefix(case().text) for t in texts]
    assert all(t.startswith(case().text) for t in texts)
    assert suffixes[0] != suffixes[1]
    assert all(set(s) <= {"\u200b", "\u200c"} for s in suffixes)


def test_post_refused_by_a_restarting_api_is_retried(
    case: Callable[..., GoldenCase],
) -> None:
    seen: list[httpx2.Request] = []
    refused = httpx2.ConnectError("connection refused")
    checks = _client([refused, _accepted(), httpx2.Response(200, json=DONE)], seen)
    run = asyncio.run(checks.check(case()))
    assert run.result.status == "done"
    assert [r.method for r in seen] == ["POST", "POST", "GET"]


def test_status_read_survives_a_bad_gateway_and_a_dropped_connection(
    case: Callable[..., GoldenCase],
) -> None:
    seen: list[httpx2.Request] = []
    dropped = httpx2.RemoteProtocolError("server disconnected")
    replies = [_accepted(), httpx2.Response(502), dropped, httpx2.Response(504)]
    checks = _client([*replies, httpx2.Response(200, json=DONE)], seen)
    run = asyncio.run(checks.check(case()))
    assert run.result.status == "done"
    assert run.check_id == DONE["check_id"]
    assert [r.method for r in seen] == ["POST", "GET", "GET", "GET", "GET"]


def test_api_that_stays_down_ends_the_case_after_a_bounded_number_of_tries(
    case: Callable[..., GoldenCase],
) -> None:
    seen: list[httpx2.Request] = []
    down = [httpx2.ConnectError("connection refused") for _ in range(50)]
    run = asyncio.run(_client(down, seen).check(case()))
    assert run.result.status == "technical_failure"
    assert len(seen) == API_RETRIES
