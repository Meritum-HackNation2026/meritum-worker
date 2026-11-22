import asyncio
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.corpus.errors import DiscoveryError, FeedUnreadableError
from meritum_worker.corpus.fakes import FakeFeedServer
from meritum_worker.corpus.feeds import canonical_url, feed_url, parse_feed
from meritum_worker.corpus.feeds.constants import MAX_PAGES_PER_ENTRY

FEEDS = Path(__file__).resolve().parents[2] / "features" / "fixtures" / "feeds"
RSS = "application/rss+xml; charset=utf-8"


def xml(name: str) -> str:
    return (FEEDS / name).read_text(encoding="utf-8")


def entry(domain: str, ingest: str) -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": domain,
            "publisher": "Urząd",
            "publisher_id": "urzad",
            "kind": "instytucja",
            "tier": "primary",
            "license": "CC BY 4.0",
            "ingest": ingest,
            "qualified_because": "Źródło z listy organizatora konkursu.",
        }
    )


def test_rss_items_come_newest_first_with_their_publication_date() -> None:
    pages = parse_feed(xml("rss.xml")).pages
    assert [p.published_on for p in pages] == [
        *[date(2026, 11, 20)] * 3,
        date(2026, 11, 19),
        date(2026, 11, 18),
    ]
    assert pages[-1].url == "https://rss.gov.pl/komunikat-1"  # no link: skipped


def test_atom_takes_the_alternate_link_and_published_or_updated() -> None:
    pages = parse_feed(xml("atom.xml")).pages
    assert [(p.url, p.published_on) for p in pages] == [
        ("https://atom.gov.pl/ostrzezenie-2", date(2026, 11, 20)),
        ("https://atom.gov.pl/ostrzezenie-1", date(2026, 11, 19)),
    ]


def test_sitemap_reads_loc_and_lastmod() -> None:
    pages = parse_feed(xml("sitemap.xml")).pages
    assert [(p.url, p.published_on) for p in pages] == [
        ("https://mapa.gov.pl/aktualnosci/b", date(2026, 11, 20)),
        ("https://mapa.gov.pl/aktualnosci/a", date(2026, 11, 17)),
        ("https://mapa.gov.pl/aktualnosci/c", None),
    ]


def test_sitemap_index_lists_children_newest_first() -> None:
    listing = parse_feed(xml("sitemap_index.xml"))
    assert listing.pages == ()
    assert listing.sitemaps == (
        "https://mapa.gov.pl/sitemap-nowe.xml",
        "https://mapa.gov.pl/sitemap-stare.xml",
    )


def test_listing_is_cut_to_the_limit() -> None:
    items = "".join(
        f"<item><link>https://rss.gov.pl/{i}</link></item>" for i in range(80)
    )
    feed = f"<rss><channel>{items}</channel></rss>"
    assert len(parse_feed(feed).pages) == MAX_PAGES_PER_ENTRY


@pytest.mark.parametrize(
    "body", [xml("entities.xml"), "<html><body>nie kanał</body></html>", "<rss"]
)
def test_unsafe_broken_or_unknown_xml_is_refused(body: str) -> None:
    with pytest.raises(FeedUnreadableError):
        parse_feed(body)


def test_canonical_url_drops_fragment_tracking_and_host_case() -> None:
    url = "HTTPS://RSS.gov.pl/Komunikat-3?id=7&utm_source=rss&UTM_x=1#top"
    assert canonical_url(url) == "https://rss.gov.pl/Komunikat-3?id=7"


def test_feed_url_comes_from_the_known_feeds_or_the_default_path() -> None:
    assert feed_url(entry("cert.pl", "rss")) == "https://cert.pl/feed/"
    assert feed_url(entry("rss.gov.pl", "rss")) == "https://rss.gov.pl/feed/"
    assert (
        feed_url(entry("mapa.gov.pl", "sitemap")) == "https://mapa.gov.pl/sitemap.xml"
    )


def test_discovery_reads_an_rss_feed_through_the_core_fetcher() -> None:
    server = FakeFeedServer()
    server.serve("https://rss.gov.pl/feed/", xml("rss.xml"), RSS)
    pages = asyncio.run(server.discovery().pages(entry("rss.gov.pl", "rss")))
    assert len(pages) == 5
    assert server.requested[0] == "https://rss.gov.pl/robots.txt"


def test_discovery_follows_a_sitemap_index() -> None:
    server = FakeFeedServer()
    server.serve(
        "https://mapa.gov.pl/sitemap.xml", xml("sitemap_index.xml"), "text/xml"
    )
    server.serve("https://mapa.gov.pl/sitemap-nowe.xml", xml("sitemap.xml"), "text/xml")
    stale = "https://mapa.gov.pl/sitemap-stare.xml"
    server.serve(stale, "<urlset/>", "application/xml")
    pages = asyncio.run(server.discovery().pages(entry("mapa.gov.pl", "sitemap")))
    assert len(pages) == 3
    assert stale in server.requested


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        (lambda s: s.answer("https://rss.gov.pl/feed/", 500), "http_error"),
        (lambda s: s.disallow("rss.gov.pl"), "robots_disallowed"),
        (
            lambda s: s.serve("https://rss.gov.pl/feed/", "<rss", RSS),
            "feed_unreadable",
        ),
        (
            lambda s: s.serve("https://rss.gov.pl/feed/", "{}", "application/json"),
            "unsupported_content",
        ),
    ],
)
def test_a_failing_feed_raises_a_discovery_error(
    setup: Callable[[FakeFeedServer], None], reason: str
) -> None:
    server = FakeFeedServer()
    setup(server)
    with pytest.raises(DiscoveryError) as raised:
        asyncio.run(server.discovery().pages(entry("rss.gov.pl", "rss")))
    assert (raised.value.url, raised.value.reason) == (
        "https://rss.gov.pl/feed/",
        reason,
    )


def test_static_entry_keeps_its_entry_page() -> None:
    server = FakeFeedServer()
    pages = asyncio.run(server.discovery().pages(entry("urzad.gov.pl", "static")))
    assert [p.url for p in pages] == ["https://urzad.gov.pl"]
    assert server.requested == []


def urlset(*locs: str) -> str:
    urls = "".join(f"<url><loc>{loc}</loc></url>" for loc in locs)
    return (
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    )


def test_pages_outside_the_entry_are_dropped() -> None:
    server = FakeFeedServer()
    server.serve(
        "https://ec.europa.eu/commission/presscorner/api/rss",
        "<rss><channel>"
        "<item><link>https://ec.europa.eu/commission/presscorner/detail/pl/ip_26_1</link></item>"
        "<item><link>https://ec.europa.eu/eurostat/news</link></item>"
        "<item><link>https://inny.example/commission/presscorner/x</link></item>"
        "</channel></rss>",
        RSS,
    )
    found = asyncio.run(
        server.discovery().pages(entry("ec.europa.eu/commission/presscorner", "rss"))
    )
    assert [p.url for p in found] == [
        "https://ec.europa.eu/commission/presscorner/detail/pl/ip_26_1"
    ]


def test_pkw_sitemap_pages_on_its_internal_host_move_to_pkw_gov_pl() -> None:
    server = FakeFeedServer()
    server.serve(
        "https://pkw.gov.pl/sitemaps/sitemap_1.xml",
        urlset(
            "http://baza57-loc.pl/kbw/petycje/2021-r",
            "https://pkw.gov.pl/aktualnosci",
            "https://obcy.example/kbw",
        ),
        "text/xml; charset=utf-8",
    )
    found = asyncio.run(server.discovery().pages(entry("pkw.gov.pl", "sitemap")))
    assert sorted(p.url for p in found) == [
        "https://pkw.gov.pl/aktualnosci",
        "https://pkw.gov.pl/kbw/petycje/2021-r",
    ]
