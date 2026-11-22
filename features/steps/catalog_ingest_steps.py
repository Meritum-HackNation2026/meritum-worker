"""Steps for the catalogue ingestion and snapshot scenarios of corpus.feature."""

import asyncio
from datetime import UTC, datetime

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.fakes import FakeCatalogSite
from meritum_worker.security import CleanInjectionDetector

PAGES_PER_DOMAIN = 8
NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)


def entry(domain: str, *, tier: str = "primary", **fields: object) -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": domain,
            "publisher": f"Wydawca {domain}",
            "publisher_id": domain.replace(".", "-"),
            "kind": "instytucja" if tier == "primary" else "fact_check",
            "tier": tier,
            "license": "CC BY 4.0",
            "ingest": "static",
            "qualified_because": "Źródło z listy organizatora konkursu.",
            "tdm_reservation": "none",
            **fields,
        }
    )


def start(context: Context, entries: list[CatalogEntry]) -> None:
    context.entries = entries
    context.site = FakeCatalogSite(pages_per_domain=PAGES_PER_DOMAIN)
    context.store = corpus.build_corpus_writer()
    context.deps = corpus.IngestDeps(
        discovery=context.site,
        fetcher=context.site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=context.store,
        injection=CleanInjectionDetector(),
    )


def ingest(context: Context, now: datetime = NOW) -> None:
    context.report = asyncio.run(
        corpus.ingest_catalog(context.entries, context.deps, now=now)
    )


@given(
    "katalog z {official:d} domenami urzędowymi i {checkers:d} domenami fact-checkerów"
)
def catalog(context: Context, official: int, checkers: int) -> None:
    primary = [entry(f"urzad{i}.gov.pl") for i in range(official)]
    secondary = [entry(f"fakty{i}.pl", tier="secondary") for i in range(checkers)]
    live = entry("api.live.gov.pl", ingest="live")
    status = entry("sankcje.gov.pl", role="source_status")
    start(context, [*primary, *secondary, live, status])


@when("workflow wczytywania katalogu kończy pierwszy przebieg")
@when("workflow wczytywania działa")
def ingestion_runs(context: Context) -> None:
    ingest(context)


@then(
    "korpus ma co najmniej {docs:d} dokumentów z co najmniej {domains:d} domen"
    " i obu typów"
)
def corpus_is_big_enough(context: Context, docs: int, domains: int) -> None:
    stored = asyncio.run(context.store.documents())
    tiers = {e.domain: e.tier for e in context.entries}
    assert len(stored) >= docs, len(stored)
    assert len({d.domain for d in stored}) >= domains
    assert {tiers[d.domain] for d in stored} == {"primary", "secondary"}
    assert not {d.domain for d in stored} & {"api.live.gov.pl", "sankcje.gov.pl"}


@then("każdy dokument ma fetched_at, publisher_id i licencję z katalogu")
def documents_carry_catalog_metadata(context: Context) -> None:
    catalog = {e.domain: e for e in context.entries}
    for document in asyncio.run(context.store.documents()):
        assert document.fetched_at == NOW
        assert document.publisher_id == catalog[document.domain].publisher_id
        assert document.license == catalog[document.domain].license


@given("pozycja katalogu z excluded = true i powodem wykluczenia")
def excluded_entry(context: Context) -> None:
    start(
        context,
        [
            entry("urzad.gov.pl"),
            entry(
                "zakazane.pl", excluded=True, exclusion_reason="robots.txt: Disallow"
            ),
            entry("tdm.gov.pl", tdm_reservation="reserved"),
            entry("meta-tdm.gov.pl"),
        ],
    )
    context.site.reserve_mining("meta-tdm.gov.pl")


@then("żaden dokument z tej domeny nie trafia do korpusu")
def nothing_from_excluded(context: Context) -> None:
    domains = {d.domain for d in asyncio.run(context.store.documents())}
    assert domains == {"urzad.gov.pl"}
    assert {d for d, _ in context.site.discovered} == {
        "urzad.gov.pl",
        "meta-tdm.gov.pl",
    }
    reasons = {f.reason for f in context.report.failures}
    assert reasons == {"tdm_reserved"}


@given(
    "korpus w wersji {version} i nowe dokumenty, także strony z wyszukiwania"
    " na żywo po skanie"
)
def corpus_with_version(context: Context, version: str) -> None:
    start(context, [entry("urzad.gov.pl")])
    ingest(context)
    old = asyncio.run(corpus.take_snapshot(context.store, scheduled=_at(version)))
    assert old.version == version
    context.old = old
    context.entries = [*context.entries, entry("nowy.gov.pl")]
    ingest(context, now=datetime(2026, 11, 20, 10, 20, tzinfo=UTC))
    page = FetchedPage(
        url="https://urzad.gov.pl/live",
        content_type="text/html",
        untrusted_text="Strona z wyszukiwania na żywo, sprawdzona skanem.",
    )
    asyncio.run(
        corpus.store_page(
            page,
            context.entries[0],
            context.deps,
            now=datetime(2026, 11, 20, 10, 40, tzinfo=UTC),
        )
    )


@when("mija termin kolejnej migawki (np. co godzinę)")
def next_snapshot(context: Context) -> None:
    scheduled = datetime(2026, 11, 20, 11, 0, tzinfo=UTC)
    context.new = asyncio.run(corpus.take_snapshot(context.store, scheduled=scheduled))


@then("powstaje nowa corpus_version z tymi dokumentami")
def new_version_has_documents(context: Context) -> None:
    assert context.new.version == "2026-11-20T11:00Z"
    stored = asyncio.run(context.store.documents())
    assert {m.source_id for m in context.new.manifest} == {d.source_id for d in stored}
    assert len(context.new.manifest) == len(context.old.manifest) + PAGES_PER_DOMAIN + 1


@then("sprawdzenia z poprzednią wersją dalej się odtwarzają")
def old_version_replays(context: Context) -> None:
    again = asyncio.run(context.store.snapshot(context.old.version))
    assert again == context.old
    assert len(context.old.manifest) == PAGES_PER_DOMAIN


def _at(version: str) -> datetime:
    return datetime.strptime(version, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
