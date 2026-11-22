"""httpx transport that hands feeds and sitemaps to core's fetcher as plain text.

Core's fetcher reads only HTML and plain text; it pins each hop's IP and SNI,
checks robots.txt and Content-Signal and caps the size before the transport
is reached, so relabelling the XML here keeps every one of those guards.

Features:
    US-KOR-03, F-13
"""

from typing import override

import httpx

from meritum_worker.corpus.feeds import FEED_AS_MEDIA_TYPE, LISTING_MEDIA_TYPES


class FeedTransport(httpx.AsyncBaseTransport):
    """Relabels RSS, Atom, XML and HTML answers as ``text/plain``, keeping the charset.

    The discovery fetcher reads only listings: feeds, sitemaps and the HTML news
    listings of gov.pl sections, whose links are in the markup.

    Args:
        inner: The transport that sends the request; a fresh
            ``httpx.AsyncHTTPTransport`` when None (tests pass a mock).

    Features:
        US-KOR-03, F-13
    """

    def __init__(self, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self._inner = inner or httpx.AsyncHTTPTransport()

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Send the request and relabel a listing's media type.

        Args:
            request: The request core's fetcher built.

        Returns:
            The response; a listing's ``content-type`` becomes ``text/plain``.
        """
        response = await self._inner.handle_async_request(request)
        declared = str(response.headers.get("content-type", ""))
        media, _, params = declared.partition(";")
        if media.strip().lower() in LISTING_MEDIA_TYPES:
            relabelled = (
                f"{FEED_AS_MEDIA_TYPE};{params}" if params else FEED_AS_MEDIA_TYPE
            )
            response.headers["content-type"] = relabelled
        return response

    @override
    async def aclose(self) -> None:
        """Close the inner transport."""
        await self._inner.aclose()
