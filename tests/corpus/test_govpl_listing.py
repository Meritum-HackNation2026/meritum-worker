import asyncio
from datetime import date
from pathlib import Path

import pytest
from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.corpus.errors import DiscoveryError
from meritum_worker.corpus.fakes import FakeFeedServer
from meritum_worker.corpus.feeds import govpl_listing_url, parse_govpl_listing

# /web/mswia/aktualnosci as gov.pl served it to MeritumBot on 2026-11-22.
LISTING = (
    Path(__file__).parent / "fixtures" / "govpl" / "mswia-aktualnosci.html"
).read_text(encoding="utf-8")
LISTING_URL = "https://www.gov.pl/web/mswia/aktualnosci"
HTML = "text/html;charset=UTF-8"


def entry(domain: str) -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": domain,
            "publisher": "Ministerstwo",
            "publisher_id": "ministerstwo",
            "kind": "instytucja",
            "tier": "primary",
            "license": "CC BY-SA 4.0 (treści tekstowe gov.pl)",
            "ingest": "static",
            "qualified_because": "Źródło z listy organizatora konkursu.",
        }
    )


def test_the_recorded_listing_gives_its_ten_articles_with_their_dates() -> None:
    pages = parse_govpl_listing(LISTING, LISTING_URL)
    assert len(pages) == 10
    assert pages[0].url == (
        "https://www.gov.pl/web/mswia/czasowe-i-terytorialne-zawieszenie-prawa-"
        "do-azylu-przy-granicy-polsko-bialoruskiej-przedluzone-o-nastepne-60-dni4"
    )
    assert pages[0].published_on == date(2026, 11, 16)
    assert all(p.published_on is not None for p in pages)
    assert len({p.url for p in pages}) == 10


def test_a_tile_without_a_date_keeps_its_link_and_no_date() -> None:
    html = (
        '<ul><li><div class="title"><a href="/web/gis/bez-daty">x</a></div></li>'
        '<li><span class="date"> 31.02.2026 </span>'
        '<div class="title"><a href="/web/gis/zla-data">y</a></div></li></ul>'
    )
    pages = parse_govpl_listing(html, "https://www.gov.pl/web/gis/aktualnosci")
    assert [(p.url, p.published_on) for p in pages] == [
        ("https://www.gov.pl/web/gis/bez-daty", None),
        ("https://www.gov.pl/web/gis/zla-data", None),
    ]


@pytest.mark.parametrize(
    ("domain", "url"),
    [
        ("www.gov.pl/web/mswia", "https://www.gov.pl/web/mswia/aktualnosci"),
        ("www.gov.pl/web/rcb", "https://www.gov.pl/web/rcb/aktualnosci"),
        (
            "www.gov.pl/web/obrona-narodowa",
            "https://www.gov.pl/web/obrona-narodowa/aktualnosci5",
        ),
        ("www.gov.pl/web/gov/ostrzezenia", None),
        ("www.gov.pl/web/dyplomacja/bip", None),
        ("www.zus.pl", None),
    ],
)
def test_only_a_whole_gov_pl_section_has_a_listing(domain: str, url: str) -> None:
    assert govpl_listing_url(entry(domain)) == url


def test_a_gov_pl_section_yields_its_entry_page_and_the_listed_articles() -> None:
    server = FakeFeedServer()
    server.serve(LISTING_URL, LISTING, HTML)
    pages = asyncio.run(server.discovery().pages(entry("www.gov.pl/web/mswia")))
    assert pages[0].url == "https://www.gov.pl/web/mswia"
    assert len(pages) == 11
    assert all(p.url.startswith("https://www.gov.pl/web/mswia/") for p in pages[1:])
    assert server.requested == ["https://www.gov.pl/robots.txt", LISTING_URL]


def test_articles_of_other_sections_on_the_listing_are_dropped() -> None:
    server = FakeFeedServer()
    server.serve(
        "https://www.gov.pl/web/gis/aktualnosci",
        '<div class="title"><a href="/web/premier/obcy">x</a></div>'
        '<div class="title"><a href="https://www.gov.pl/web/gis/swoj">y</a></div>',
        HTML,
    )
    pages = asyncio.run(server.discovery().pages(entry("www.gov.pl/web/gis")))
    assert [p.url for p in pages] == [
        "https://www.gov.pl/web/gis",
        "https://www.gov.pl/web/gis/swoj",
    ]


def test_a_failing_listing_raises_a_discovery_error() -> None:
    server = FakeFeedServer()
    server.answer(LISTING_URL, 500)
    with pytest.raises(DiscoveryError) as raised:
        asyncio.run(server.discovery().pages(entry("www.gov.pl/web/mswia")))
    assert (raised.value.url, raised.value.reason) == (LISTING_URL, "http_error")


def test_a_gov_pl_subpage_keeps_only_its_entry_page() -> None:
    server = FakeFeedServer()
    found = asyncio.run(
        server.discovery().pages(entry("www.gov.pl/web/dyplomacja/bip"))
    )
    assert [p.url for p in found] == ["https://www.gov.pl/web/dyplomacja/bip"]
    assert server.requested == []
