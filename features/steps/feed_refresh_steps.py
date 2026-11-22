"""Steps for the RSS and sitemap refresh scenarios of corpus.feature (US-KOR-03)."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.fakes import FakeCatalogSite, FakeFeedServer
from meritum_worker.security import CleanInjectionDetector

FEEDS = Path(__file__).resolve().parents[1] / "fixtures" / "feeds"
RSS = "application/rss+xml; charset=utf-8"
NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
NEW_ITEMS = 3


def feed(name: str) -> str:
    return (FEEDS / name).read_text(encoding="utf-8")


def entry(domain: str, ingest: str = "static", **fields: object) -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": domain,
            "publisher": f"Wydawca {domain}",
            "publisher_id": domain.replace(".", "-"),
            "kind": "instytucja",
            "tier": "primary",
            "license": "CC BY 4.0",
            "ingest": ingest,
            "qualified_because": "Źródło z listy organizatora konkursu.",
            "tdm_reservation": "none",
            **fields,
        }
    )


def start_feeds(context: Context, entries: list[CatalogEntry]) -> None:
    context.entries = entries
    context.feeds = FakeFeedServer()
    context.site = FakeCatalogSite(pages_per_domain=1)
    context.store = corpus.build_corpus_writer()
    context.deps = corpus.IngestDeps(
        discovery=context.feeds.discovery(),
        fetcher=context.site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=context.store,
        injection=CleanInjectionDetector(),
    )


def run(context: Context, at: datetime) -> None:
    context.report = asyncio.run(
        corpus.ingest_catalog(context.entries, context.deps, now=at)
    )


def stored(context: Context) -> dict[str, date | None]:
    return {d.url: d.published_on for d in asyncio.run(context.store.documents())}


@given("pozycja katalogu z kanałem RSS i 3 nowymi wpisami od ostatniego przebiegu")
def rss_with_new_items(context: Context) -> None:
    start_feeds(context, [entry("rss.gov.pl", "rss", refresh_minutes=15)])
    context.feeds.serve("https://rss.gov.pl/feed/", feed("rss_previous.xml"), RSS)
    run(context, NOW)
    context.before = stored(context)
    context.site.fetched.clear()
    context.feeds.serve("https://rss.gov.pl/feed/", feed("rss.xml"), RSS)


@when("cykliczny workflow DBOS uruchamia się po 20 minutach")
def runs_twenty_minutes_later(context: Context) -> None:
    run(context, NOW + timedelta(minutes=20))


@then("3 nowe dokumenty trafiają do korpusu z datą publikacji z kanału")
def three_new_documents(context: Context) -> None:
    added = {u: d for u, d in stored(context).items() if u not in context.before}
    assert added == {
        "https://rss.gov.pl/komunikat-2": date(2026, 11, 19),
        "https://rss.gov.pl/komunikat-3": date(2026, 11, 20),
        "https://rss.gov.pl/komunikat-4": date(2026, 11, 20),
    }, added
    assert context.report.added == NEW_ITEMS


@then("wpisy już wczytane i powtórzone z innym znacznikiem nie są pobierane ponownie")
def known_and_repeated_items_are_skipped(context: Context) -> None:
    fetched = [url for url, _ in context.site.fetched]
    assert len(fetched) == len(set(fetched)) == NEW_ITEMS, fetched
    assert "https://rss.gov.pl/komunikat-1" not in fetched


@given("wczytywanie RSS pobrało dokument z kanału z katalogu")
def rss_and_static_entries(context: Context) -> None:
    start_feeds(context, [entry("rss.gov.pl", "rss"), entry("urzad.gov.pl")])
    context.feeds.serve("https://rss.gov.pl/feed/", feed("rss.xml"), RSS)


@when("magazyn korpusu zapisuje dokument")
def store_saves_documents(context: Context) -> None:
    run(context, NOW)


@then(
    'dokument z kanału ma via "rss", a dokument z wczytywania katalogu ma via "corpus"'
)
def documents_keep_their_via(context: Context) -> None:
    documents = asyncio.run(context.store.documents())
    by_domain = {(d.domain, d.via) for d in documents}
    assert by_domain == {("rss.gov.pl", "rss"), ("urzad.gov.pl", "corpus")}, by_domain


@given("pozycja katalogu z indeksem map strony")
def sitemap_index(context: Context) -> None:
    start_feeds(context, [entry("mapa.gov.pl", "sitemap")])
    serve = context.feeds.serve
    serve("https://mapa.gov.pl/sitemap.xml", feed("sitemap_index.xml"), "text/xml")
    serve("https://mapa.gov.pl/sitemap-nowe.xml", feed("sitemap.xml"), "text/xml")
    serve("https://mapa.gov.pl/sitemap-stare.xml", "<urlset/>", "application/xml")


@when("workflow odświeżania działa")
def refresh_runs(context: Context) -> None:
    run(context, NOW)


@then("adresy z map podrzędnych trafiają do korpusu z datą lastmod")
def sitemap_pages_are_stored(context: Context) -> None:
    assert stored(context) == {
        "https://mapa.gov.pl/aktualnosci/a": date(2026, 11, 17),
        "https://mapa.gov.pl/aktualnosci/b": date(2026, 11, 20),
        "https://mapa.gov.pl/aktualnosci/c": None,
    }


@given("kanał RSS zwraca błąd 500")
def rss_answers_500(context: Context) -> None:
    broken, static, working = "awaria.gov.pl", "urzad.gov.pl", "rss.gov.pl"
    start_feeds(context, [entry(broken, "rss"), entry(static), entry(working, "rss")])
    context.feeds.answer(f"https://{broken}/feed/", 500)
    context.feeds.serve(f"https://{working}/feed/", feed("rss.xml"), RSS)


@then("błąd jest zapisany z domeną i czasem, a pozostałe źródła są odświeżone")
def failure_is_recorded_and_others_refresh(context: Context) -> None:
    (failure,) = context.report.failures
    assert (failure.domain, failure.url, failure.reason, failure.at) == (
        "awaria.gov.pl",
        "https://awaria.gov.pl/feed/",
        "http_error",
        NOW,
    )
    domains = {d.domain for d in asyncio.run(context.store.documents())}
    assert domains == {"urzad.gov.pl", "rss.gov.pl"}
