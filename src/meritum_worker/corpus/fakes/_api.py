"""A fake set of public APIs behind core's real fetcher, no network.

Requests go through ``build_page_fetcher`` and ``JsonAsTextTransport`` like in
production; only DNS and the socket are replaced.

Features:
    US-KOR-02, F-10, F-12
"""

import ipaddress

import httpx
from meritum_core.corpus.fetching import PageFetcherPort, build_page_fetcher
from meritum_core.corpus.fetching.ports import IpAddress

from meritum_worker.corpus.adapters import JsonAsTextTransport


class FakePublicApi:
    """Answers recorded per URL; robots.txt and other URLs answer 404.

    Attributes:
        requested: Every requested URL (host name, not the pinned IP), in order.

    Features:
        US-KOR-02, F-10, F-12
    """

    def __init__(self) -> None:
        self._answers: dict[str, tuple[int, str, str]] = {}
        self.requested: list[str] = []

    def answer(
        self,
        url: str,
        body: str,
        *,
        status: int = 200,
        content_type: str = "application/json",
    ) -> None:
        """Record what one URL answers.

        Args:
            url: The full request URL, query included.
            body: The response body.
            status: The HTTP status.
            content_type: The response's media type.
        """
        self._answers[url] = (status, content_type, body)

    def fetcher(self) -> PageFetcherPort:
        """Core's fetcher, as ``build_api_fetcher`` builds it, over this fake.

        Returns:
            The fetcher.
        """
        transport = JsonAsTextTransport(lambda: httpx.MockTransport(self._handle))
        return build_page_fetcher(resolver=_public, transport=transport)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        url = f"https://{request.headers['host']}{request.url.raw_path.decode()}"
        self.requested.append(url)
        status, content_type, body = self._answers.get(url, (404, "text/plain", ""))
        return httpx.Response(status, headers={"content-type": content_type}, text=body)


async def _public(_host: str) -> list[IpAddress]:  # ruff: ignore[unused-async]  # the resolver port is async
    return [ipaddress.ip_address("93.184.215.14")]
