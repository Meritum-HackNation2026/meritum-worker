"""httpx transport that hands JSON answers to core's page fetcher as plain text.

Core's fetcher reads only HTML and plain text. It pins every hop to a checked
public address, sets SNI and reads robots.txt before the request reaches this
transport, so relabelling ``application/json`` (and ``+json`` types) as
``text/plain`` keeps the SSRF guard and gives the raw JSON as ``untrusted_text``.

Features:
    US-KOR-02, US-SPR-07, F-06, F-10, F-12, ADR-32
"""

from collections.abc import Callable
from typing import override

import httpx
from meritum_core.corpus.fetching import PageFetcherPort, build_page_fetcher

from meritum_worker.corpus.adapters._pdf_transport import PdfAsTextTransport
from meritum_worker.corpus.catalog_api.constants import (
    API_RECORD_CONTENT_TYPE,
    JSON_DEFAULT_CHARSET,
    JSON_MEDIA_SUFFIX,
    JSON_RELABELLED_TYPE,
)


class JsonAsTextTransport(httpx.AsyncBaseTransport):
    """Wraps a transport; a JSON answer comes back labelled ``text/plain``.

    Args:
        make_inner: Builds the wrapped transport; ``httpx.AsyncHTTPTransport``
            unless a test passes a mock. Built again after ``aclose``, because
            the fetcher closes its client, and so the transport, after each page.

    Features:
        US-KOR-02, US-SPR-07, F-06, F-10, F-12, ADR-32
    """

    def __init__(
        self,
        make_inner: Callable[[], httpx.AsyncBaseTransport] = httpx.AsyncHTTPTransport,
    ) -> None:
        self._make_inner = make_inner
        self._inner: httpx.AsyncBaseTransport | None = None

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Send the request; relabel a JSON answer as plain text.

        Args:
            request: The pinned request core's fetcher built.

        Returns:
            The answer; a JSON one with ``text/plain`` and its charset.
        """
        if self._inner is None:
            self._inner = self._make_inner()
        response = await self._inner.handle_async_request(request)
        media, _, params = response.headers.get("content-type", "").partition(";")
        media = media.strip().lower()
        if media != API_RECORD_CONTENT_TYPE and not media.endswith(JSON_MEDIA_SUFFIX):
            return response
        headers = [
            (name, value)
            for name, value in response.headers.multi_items()
            if name.lower() != "content-type"
        ]
        headers.append(
            (
                "content-type",
                f"{JSON_RELABELLED_TYPE}; {params.strip() or JSON_DEFAULT_CHARSET}",
            )
        )
        return httpx.Response(
            response.status_code,
            headers=headers,
            stream=response.stream,
            extensions=response.extensions,
        )

    @override
    async def aclose(self) -> None:
        inner, self._inner = self._inner, None
        if inner is not None:
            await inner.aclose()


def build_api_fetcher() -> PageFetcherPort:
    """Build core's SSRF-safe fetcher for public JSON APIs.

    Returns:
        The fetcher over a transport that labels JSON answers ``text/plain``
        and turns PDF answers into their text; pinning, SNI and robots.txt
        stay core's.

    Features:
        US-KOR-02, US-SPR-07, F-06, F-10, F-12, ADR-32
    """
    return build_page_fetcher(transport=JsonAsTextTransport(PdfAsTextTransport))
