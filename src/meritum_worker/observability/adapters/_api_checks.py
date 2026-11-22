"""Cases checked through a running Meritum API, e.g. dev with real providers.

Features:
    US-OBS-04, US-OBS-05, F-27, ADR-28
"""

import asyncio
import secrets
import time

from httpx2 import AsyncClient, HTTPError, Response, TransportError
from meritum_core.checks import CheckResult
from pydantic import BaseModel, ValidationError

from meritum_worker.observability.constants import (
    API_CHECKS_PATH,
    API_POLL_SECONDS,
    API_REQUEST_TIMEOUT_SECONDS,
    API_RETRIES,
    API_RETRY_AFTER_SECONDS,
    API_SESSION_HEADER,
    API_TIMEOUT_SECONDS,
    CACHE_TAG_BITS,
    CACHE_TAG_DIGITS,
    FAILURE_CODE,
    FAILURE_MESSAGE,
    NO_CORPUS_VERSION,
    RATE_LIMITED,
    RETRY_STATUSES,
)
from meritum_worker.observability.models import GoldenCase
from meritum_worker.observability.report import CaseRun


class _Accepted(BaseModel):
    check_id: str


class _Status(BaseModel):
    result: CheckResult | None = None


class ApiChecks:
    """Post each case as a web check and poll its status until the result.

    Time is the wall clock from the post to the result, as a user sees it;
    tokens and cost stay in the API's CheckRecord, not in the answer.

    Args:
        base_url: The API's origin, e.g. ``https://meritum-dev.gburek.app``.
        client: The HTTP client (a recorded API in tests); None: its own, closed
            by ``aclose``.
        poll_seconds: Pause between status reads, and before a retry after a
            dropped connection or a 502, 503 or 504 (the API restarting mid-run).
        timeout_seconds: Longest wait for a result; then a technical failure.
        fresh: Tag every text with this run's invisible suffix, so the API's
            result cache (keyed by the normalized text) misses and the check runs.

    Features:
        US-OBS-04, US-OBS-05, F-27, ADR-28
    """

    def __init__(
        self,
        base_url: str,
        client: AsyncClient | None = None,
        *,
        poll_seconds: float = API_POLL_SECONDS,
        timeout_seconds: float = API_TIMEOUT_SECONDS,
        fresh: bool = False,
    ) -> None:
        self._url = base_url.rstrip("/") + API_CHECKS_PATH
        self._client = client or AsyncClient(timeout=API_REQUEST_TIMEOUT_SECONDS)
        self._poll = poll_seconds
        self._timeout = timeout_seconds
        # Zero-width characters change the cache key, not what the model reads.
        tag = secrets.randbits(CACHE_TAG_BITS) if fresh else None
        self._suffix = (
            ""
            if tag is None
            else f"{tag:0{CACHE_TAG_BITS}b}".translate(CACHE_TAG_DIGITS)
        )

    async def check(self, case: GoldenCase) -> CaseRun:
        """Check one case; any API failure ends it as a technical failure.

        Args:
            case: The case; its text and link go as a web check.

        Returns:
            The run with the API's result and the wall-clock time.
        """
        started = time.monotonic()
        check_id = ""
        try:
            check_id = await self._start(case)
            async with asyncio.timeout(self._timeout):
                result = await self._result(check_id)
        except HTTPError, ValidationError, TimeoutError:
            result = _failure(check_id)
        seconds = time.monotonic() - started
        return CaseRun(case=case, result=result, seconds=seconds, check_id=check_id)

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _start(self, case: GoldenCase) -> str:
        text = None if case.text is None else case.text + self._suffix
        body = {"channel": "web", "text": text, "url": case.url}
        payload = {k: str(v) for k, v in body.items() if v is not None}
        headers = {API_SESSION_HEADER: secrets.token_hex(16)}
        response = await self._send("POST", self._url, payload, headers)
        return _Accepted.model_validate_json(response.content).check_id

    async def _result(self, check_id: str) -> CheckResult:
        while True:
            response = await self._send("GET", f"{self._url}/{check_id}")
            status = _Status.model_validate_json(response.content)
            if status.result is not None:
                return status.result
            await asyncio.sleep(self._poll)

    async def _send(
        self,
        method: str,
        url: str,
        payload: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        # A restarting API refuses or drops connections for under a minute.
        for _ in range(API_RETRIES - 1):
            try:
                response = await self._client.request(
                    method, url, json=payload, headers=headers
                )
            except TransportError:
                await asyncio.sleep(self._poll)
                continue
            if response.status_code not in RETRY_STATUSES:
                break
            await asyncio.sleep(self._pause(response))
        else:  # the last try: its error ends the case
            response = await self._client.request(
                method, url, json=payload, headers=headers
            )
        response.raise_for_status()
        return response

    def _pause(self, response: Response) -> float:
        limited = response.status_code == RATE_LIMITED
        default = API_RETRY_AFTER_SECONDS if limited else self._poll
        return float(response.headers.get("Retry-After", default))


def _failure(check_id: str) -> CheckResult:
    return CheckResult(
        check_id=check_id or "none",
        status="technical_failure",
        message=FAILURE_MESSAGE,
        failure_code=FAILURE_CODE,
        corpus_version=NO_CORPUS_VERSION,
    )
