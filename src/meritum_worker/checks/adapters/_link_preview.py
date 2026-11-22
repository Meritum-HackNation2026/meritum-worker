"""httpx transport that hands a video or post page to core's fetcher as its preview.

Pages of video and social services hold an application, so core's main-text
extraction returns the footer, the replies or nothing. Like the corpus PDF
transport, this sits below core's SSRF guard: an HTML answer from such a
service comes back as ``text/plain`` holding the title and description the
service publishes for link previews.

Features:
    US-SPR-07, F-06, ADR-12
"""

from collections.abc import Callable
from typing import override

import httpx

from meritum_worker.checks.links.constants import (
    HTML_MEDIA_TYPE,
    PAGE_TOO_LARGE_STATUS,
    PREVIEW_MAX_BYTES,
    PREVIEW_MEDIA_TYPE,
)
from meritum_worker.checks.links.previews import is_preview_host, preview_text


class LinkPreviewTransport(httpx.AsyncBaseTransport):
    """Wraps a transport; a video or post page comes back as its preview text.

    A page with no preview comes back empty, which the check reports as a link
    it could not read; a page over ``PREVIEW_MAX_BYTES`` answers 413. Other
    hosts and media types pass through.

    Args:
        make_inner: Builds the wrapped transport; ``httpx.AsyncHTTPTransport``
            unless a test passes a mock. Built again after ``aclose``, because
            the fetcher closes its client, and so the transport, after each page.

    Features:
        US-SPR-07, F-06, ADR-12
    """

    def __init__(
        self,
        make_inner: Callable[[], httpx.AsyncBaseTransport] = httpx.AsyncHTTPTransport,
    ) -> None:
        self._make_inner = make_inner
        self._inner: httpx.AsyncBaseTransport | None = None

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Send the request; turn a video or post page into its preview text.

        Args:
            request: The pinned request core's fetcher built.

        Returns:
            The answer; a preview one as ``text/plain`` in UTF-8.
        """
        if self._inner is None:
            self._inner = self._make_inner()
        response = await self._inner.handle_async_request(request)
        media = response.headers.get("content-type", "").partition(";")[0]
        is_page = response.is_success and media.strip().lower() == HTML_MEDIA_TYPE
        if not is_page or not is_preview_host(request.headers.get("host")):
            return response
        data = await _read(response)
        if data is None:
            return httpx.Response(PAGE_TOO_LARGE_STATUS)
        text = preview_text(data.decode(response.encoding or "utf-8", "replace"))
        return httpx.Response(
            response.status_code,
            headers={"content-type": PREVIEW_MEDIA_TYPE},
            content=text.encode(),
        )

    @override
    async def aclose(self) -> None:
        inner, self._inner = self._inner, None
        if inner is not None:
            await inner.aclose()


async def _read(response: httpx.Response) -> bytes | None:
    data = bytearray()
    try:
        async for chunk in response.aiter_bytes():  # decoded if compressed
            data += chunk
            if len(data) > PREVIEW_MAX_BYTES:
                return None
    finally:
        await response.aclose()
    return bytes(data)
