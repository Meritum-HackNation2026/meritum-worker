import asyncio
from datetime import date
from pathlib import Path

import pytest
from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.corpus.errors import FeedUnreadableError
from meritum_worker.corpus.fakes import FakeFeedServer
from meritum_worker.corpus.feeds import feed_url, parse_feed

# Recorded 2026-11-22 from NATO's news listing, cut to three articles and to the
# fields the discovery reads.
LISTING = (
    Path(__file__).resolve().parent / "fixtures" / "feeds" / "nato-news.json"
).read_text(encoding="utf-8")
NEWS = (
    "https://www.nato.int/content/nato/en/news-and-events/articles/news"
    "/jcr:content/root/container/general_search.search.json"
)
ARTICLE = "https://www.nato.int/en/news-and-events/articles/news/2026/11/19/"


def nato() -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": "www.nato.int",
            "publisher": "NATO",
            "publisher_id": "nato",
            "kind": "instytucja",
            "tier": "primary",
            "license": "warunki nato.int",
            "ingest": "sitemap",
            "qualified_because": "Stanowiska NATO.",
        }
    )


def test_nato_news_listing_gives_english_articles_with_their_date() -> None:
    pages = parse_feed(LISTING).pages
    assert [p.url for p in pages] == [
        f"{ARTICLE}nato-and-cyber-industry-leaders-discuss-enhanced-cooperation-for-cyberspace-defence",
        f"{ARTICLE}nato-comeds-66th-plenary-health-is-security",
        f"{ARTICLE}allies-strengthen-medical-support-for-natos-collective-defence",
    ]
    assert {p.published_on for p in pages} == {date(2026, 11, 19)}


def test_nato_is_read_from_its_english_news_listing() -> None:
    assert feed_url(nato()).startswith(f"{NEWS}?")
    assert "sortBy=dateDesc" in feed_url(nato())


def test_discovery_reads_the_nato_listing_through_the_core_fetcher() -> None:
    server = FakeFeedServer()
    server.serve(NEWS, LISTING, "application/json;charset=utf-8")
    pages = asyncio.run(server.discovery().pages(nato()))
    assert len(pages) == 3
    assert all(p.url.startswith(ARTICLE) for p in pages)


@pytest.mark.parametrize("body", ["{}", '{"pages": [{"title": "x"}]}', "[1]", "{"])
def test_json_that_is_no_news_listing_is_refused(body: str) -> None:
    with pytest.raises(FeedUnreadableError):
        parse_feed(body)
