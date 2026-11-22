"""The media search on OpenRouter's web plugin, on a reply in the documented shape.

The fixture follows OpenRouter's web search reference (``url_citation``
annotations); it is not a capture of a real call.
"""

import asyncio
import json
from pathlib import Path

import httpx2
import pytest
from meritum_core.corpus.web_search import WebSearchPort, WebSearchUnavailableError
from meritum_core.security import MaskedText
from pydantic import SecretStr

from meritum_worker.checks.adapters import OpenRouterNewsSearch
from meritum_worker.checks.news import news_catalog

FIXTURE = Path(__file__).parent / "fixtures" / "openrouter-web-search.json"
QUERY = MaskedText(text="sciopero generale Italia novembre 2026", replaced=0)
SKY = "https://tg24.sky.it/cronaca/2026/11/18/sciopero-20-novembre-2026"
ANSA = "https://www.ansa.it/sito/notizie/economia/2026/11/17/sciopero.html"


def _search(
    status: int = 200, body: bytes | None = None
) -> tuple[WebSearchPort, list[httpx2.Request]]:
    sent: list[httpx2.Request] = []

    def reply(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(status, content=body or FIXTURE.read_bytes())

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    search = OpenRouterNewsSearch(
        SecretStr("or-recorded"),
        news_catalog(),
        model="anthropic/claude-haiku-5.5",
        base_url="https://openrouter.ai/api/v1",
        http_client=client,
    )
    return search, sent


def test_only_addresses_of_listed_outlets_come_back_each_once() -> None:
    search, _ = _search()
    found = asyncio.run(search.search(QUERY, limit=5))
    assert [(c.url, c.publisher_id) for c in found] == [
        (SKY, "sky-tg24"),
        (ANSA, "ansa"),
    ]


def test_one_call_asks_exa_for_five_results_on_the_outlets_only() -> None:
    search, sent = _search()
    found = asyncio.run(search.search(QUERY, limit=1))
    assert [c.url for c in found] == [SKY]
    (request,) = sent
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    body = json.loads(request.content)
    (plugin,) = body["plugins"]
    assert (plugin["id"], plugin["engine"], plugin["max_results"]) == ("web", "exa", 5)
    assert "tg24.sky.it" in plugin["include_domains"]
    assert len(plugin["include_domains"]) == 21
    assert body["messages"] == [{"role": "user", "content": QUERY.text}]
    assert body["provider"]["data_collection"] == "deny"
    assert request.headers["authorization"] == "Bearer or-recorded"


@pytest.mark.parametrize(
    ("status", "body"), [(503, b"{}"), (200, b"not json"), (200, b'{"choices": []}')]
)
def test_a_failed_or_unreadable_reply_is_a_web_search_error(
    status: int, body: bytes
) -> None:
    search, _ = _search(status, body)
    with pytest.raises(WebSearchUnavailableError):
        asyncio.run(search.search(QUERY))
