"""A case checked through the Meritum API, as on dev (worker#170)."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import httpx2

from meritum_worker.observability import GoldenCase
from meritum_worker.observability.adapters import ApiChecks

DONE = json.loads(
    (Path(__file__).parent / "fixtures" / "api_check_done.json").read_text("utf-8")
)
BASE = "https://meritum.example"
PENDING = {"check_id": DONE["check_id"], "steps": [], "result": None}


def _client(
    replies: list[httpx2.Response],
    seen: list[httpx2.Request],
    poll_seconds: float = 0,
    timeout_seconds: float = 5,
) -> ApiChecks:
    def reply(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return replies.pop(0)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    return ApiChecks(
        BASE, client, poll_seconds=poll_seconds, timeout_seconds=timeout_seconds
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
