"""The last-resort search in major media, after the catalogue gave nothing."""

import asyncio
import dataclasses

from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage, FetchPurpose
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.evidence.models import SourceDocument
from tests.checks.conftest import MakeDeps

from meritum_worker.checks import CheckDeps, CheckState
from meritum_worker.checks.news import news_catalog
from meritum_worker.checks.steps import search_news
from meritum_worker.corpus import FakeWebSearch

URL = "https://tg24.sky.it/cronaca/2026/11/18/sciopero-20-novembre-2026"
TEXT = "Sciopero generale proclamato per il 20 novembre 2026."


class _Pages:
    async def fetch(  # ruff: ignore[no-self-use]  # same signature as the port
        self, url: str, *, purpose: FetchPurpose
    ) -> FetchedPage:
        del purpose
        return FetchedPage(url=url, content_type="text/html", untrusted_text=TEXT)


def _deps(make_deps: MakeDeps) -> tuple[CheckDeps, FakeWebSearch]:
    news = FakeWebSearch(
        (WebSearchCandidate(url=URL, domain="tg24.sky.it", publisher_id="sky-tg24"),)
    )
    deps = dataclasses.replace(
        make_deps(),
        news_search=news,
        pages=_Pages(),
        catalog=(*load_catalog(), *news_catalog()),
    )
    return deps, news


def test_a_fact_nothing_was_found_for_gets_one_search_in_major_media(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps, news = _deps(make_deps)
    out = asyncio.run(search_news(state, deps))
    (document,) = out.evidence
    assert (document.source.publisher, document.source.kind, document.source.tier) == (
        "Sky TG24",
        "media",
        "secondary",
    )
    assert len(news.queries) == 1
    assert out.web_search_calls == state.web_search_calls + 1


def test_media_are_not_asked_when_the_catalogue_search_found_a_page(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps, news = _deps(make_deps)
    found = asyncio.run(search_news(state, deps)).evidence
    assert all(isinstance(d, SourceDocument) for d in found)
    out = asyncio.run(search_news(state.model_copy(update={"evidence": found}), deps))
    assert out.evidence == found
    assert len(news.queries) == 1


def test_the_list_holds_the_agreed_outlets_as_secondary_media() -> None:
    entries = news_catalog()
    assert len(entries) == 21
    assert {(e.kind, e.tier, e.ingest) for e in entries} == {
        ("media", "secondary", "live")
    }
