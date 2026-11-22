"""Recorded pages behind the checks' page fetcher for tests and behave: no network."""

import ipaddress
from collections.abc import Mapping

import httpx
from meritum_core.corpus.fetching import PageFetcherPort
from meritum_core.corpus.fetching.ports import IpAddress

from meritum_worker.checks.factory import build_link_fetcher


def recorded_pages(pages: Mapping[str, bytes]) -> PageFetcherPort:
    """The fetcher ``build_check_deps`` builds, answering from recorded pages.

    A body that starts as a PDF answers ``application/pdf``, any other as HTML.
    Any other URL answers 404; every host resolves to one public address.
    """

    def handle(request: httpx.Request) -> httpx.Response:
        url = f"https://{request.headers['host']}{request.url.raw_path.decode()}"
        if url not in pages:
            return httpx.Response(404)
        is_pdf = pages[url].startswith(b"%PDF")
        media = "application/pdf" if is_pdf else "text/html; charset=utf-8"
        headers = {"content-type": media}
        return httpx.Response(200, headers=headers, content=pages[url])

    return build_link_fetcher(_public, lambda: httpx.MockTransport(handle))


async def _public(_host: str) -> list[IpAddress]:  # ruff: ignore[unused-async]  # the resolver port is async
    return [ipaddress.ip_address("93.184.215.14")]
