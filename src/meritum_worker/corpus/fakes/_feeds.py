"""A fake web server of feeds and sitemaps behind the real feed discovery, no network.

Features:
    US-KOR-03, F-13
"""

import ipaddress

import httpx
from meritum_core.corpus.fetching import build_page_fetcher

from meritum_worker.corpus.adapters import FeedDiscovery, FeedTransport


class FakeFeedServer:
    """Serves XML files by URL through core's fetcher and ``FeedTransport``.

    Every host resolves to one documentation address; robots.txt is missing
    (all allowed) unless ``disallow`` is called.

    Attributes:
        requested: Every requested URL (scheme, host header, path), in order.

    Features:
        US-KOR-03, F-13
    """

    def __init__(self) -> None:
        self._files: dict[str, tuple[str, str]] = {}
        self._statuses: dict[str, int] = {}
        self._robots: dict[str, str] = {}
        self.requested: list[str] = []

    def serve(self, url: str, xml: str, content_type: str) -> None:
        """Serve ``xml`` at ``url`` with this media type.

        Args:
            url: Absolute URL without a query string.
            xml: The body.
            content_type: The ``content-type`` header.
        """
        self._files[url] = (content_type, xml)

    def answer(self, url: str, status: int) -> None:
        """Answer ``url`` with an empty response of this status.

        Args:
            url: Absolute URL without a query string.
            status: The HTTP status, e.g. 500.
        """
        self._statuses[url] = status

    def disallow(self, host: str) -> None:
        """Serve a robots.txt on ``host`` that disallows everything.

        Args:
            host: The host name.
        """
        self._robots[host] = "User-agent: *\nDisallow: /\n"

    def discovery(self) -> FeedDiscovery:
        """Build the real feed discovery on this server.

        Returns:
            ``FeedDiscovery`` on core's fetcher over ``FeedTransport``.
        """
        transport = FeedTransport(httpx.MockTransport(self._handle))
        return FeedDiscovery(build_page_fetcher(resolver=_resolve, transport=transport))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        host = request.headers["host"]
        url = f"{request.url.scheme}://{host}{request.url.path}"
        self.requested.append(url)
        if request.url.path == "/robots.txt":
            robots = self._robots.get(host)
            return (
                httpx.Response(404)
                if robots is None
                else httpx.Response(200, text=robots)
            )
        if url in self._statuses:
            return httpx.Response(self._statuses[url])
        if url not in self._files:
            return httpx.Response(404)
        content_type, xml = self._files[url]
        return httpx.Response(
            200, content=xml.encode(), headers={"content-type": content_type}
        )


async def _resolve(_host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:  # ruff: ignore[unused-async]  # core awaits its resolver
    return [
        ipaddress.ip_address("93.184.216.34")
    ]  # any public address; nothing connects
