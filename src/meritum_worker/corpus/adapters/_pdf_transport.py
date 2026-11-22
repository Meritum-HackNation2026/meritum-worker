"""httpx transport that hands a PDF answer to core's page fetcher as plain text.

Core's fetcher reads only HTML and plain text, and the Sejm's ELI API has the
text of most acts only in PDF. Like ``JsonAsTextTransport``, this sits below
core's SSRF guard and robots.txt check: a PDF answer comes back as
``text/plain``, its pages' text separated by a form feed. PDFium (pypdfium2)
reads it, off the event loop and one document at a time, since PDFium is not
thread-safe.

Features:
    US-KOR-02, US-ZRD-05, F-10, F-12, ADR-32
"""

import asyncio
import threading
from collections.abc import Callable
from functools import cache
from typing import override

import httpx
import pypdfium2

from meritum_worker.corpus.catalog_api.constants import (
    JSON_DEFAULT_CHARSET,
    JSON_RELABELLED_TYPE,
    PDF_CONTENT_TYPE,
    PDF_MAX_BYTES,
    PDF_PAGE_BREAK,
    PDF_TOO_LARGE_STATUS,
)


@cache
def _pdfium() -> threading.Lock:
    return threading.Lock()  # one per process: PDFium is not thread-safe


def pdf_text(data: bytes) -> str:
    """The text layer of a PDF, page by page.

    Args:
        data: The PDF file (untrusted).

    Returns:
        Each page's text, joined by ``PDF_PAGE_BREAK``; blank for a scan.

    Raises:
        pypdfium2.PdfiumError: The bytes are not a PDF PDFium can open.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """  # ruff: ignore[docstring-extraneous-exception]  # raised by PdfDocument
    with _pdfium():
        document = pypdfium2.PdfDocument(data)
        try:
            pages: list[str] = [
                str(page.get_textpage().get_text_bounded()) for page in document
            ]
            return PDF_PAGE_BREAK.join(pages)
        finally:
            document.close()


class PdfAsTextTransport(httpx.AsyncBaseTransport):
    """Wraps a transport; a PDF answer comes back as its text, ``text/plain``.

    A PDF over ``PDF_MAX_BYTES`` answers 413; one PDFium cannot open keeps its
    media type, so core reports ``unsupported_content``.

    Args:
        make_inner: Builds the wrapped transport; ``httpx.AsyncHTTPTransport``
            unless a test passes a mock. Built again after ``aclose``.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12, ADR-32
    """

    def __init__(
        self,
        make_inner: Callable[[], httpx.AsyncBaseTransport] = httpx.AsyncHTTPTransport,
    ) -> None:
        self._make_inner = make_inner
        self._inner: httpx.AsyncBaseTransport | None = None

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Send the request; turn a PDF answer into its text.

        Args:
            request: The pinned request core's fetcher built.

        Returns:
            The answer; a PDF one as ``text/plain`` in UTF-8.
        """
        if self._inner is None:
            self._inner = self._make_inner()
        response = await self._inner.handle_async_request(request)
        media = response.headers.get("content-type", "").partition(";")[0]
        if media.strip().lower() != PDF_CONTENT_TYPE or not response.is_success:
            return response
        data = await _read(response)
        if data is None:
            return httpx.Response(PDF_TOO_LARGE_STATUS)
        try:
            text = await asyncio.to_thread(pdf_text, data)
        except pypdfium2.PdfiumError:
            return httpx.Response(
                response.status_code,
                headers={"content-type": PDF_CONTENT_TYPE},
                content=data,
            )
        return httpx.Response(
            response.status_code,
            headers={"content-type": f"{JSON_RELABELLED_TYPE}; {JSON_DEFAULT_CHARSET}"},
            content=text.encode(),
        )

    @override
    async def aclose(self) -> None:
        inner, self._inner = self._inner, None
        if inner is not None:
            await inner.aclose()


async def _read(response: httpx.Response) -> bytes | None:
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > PDF_MAX_BYTES:
        await response.aclose()
        return None
    data = bytearray()
    try:
        async for chunk in response.aiter_bytes():  # decoded if compressed
            data += chunk
            if len(data) > PDF_MAX_BYTES:
                return None
    finally:
        await response.aclose()
    return bytes(data)
