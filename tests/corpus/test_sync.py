"""The EUvsDisinfo sync writes a difference; tested on the fake MCP server."""

import asyncio
from datetime import UTC, datetime

import pytest
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.constants import MAX_PAGES
from meritum_worker.corpus.fakes import FakeEuvsDisinfoServer

TOKEN = "token"  # ruff: ignore[hardcoded-password-string]  # the fake server's token
NOW = datetime(2026, 11, 21, tzinfo=UTC)


def sync(
    server: FakeEuvsDisinfoServer, store: corpus.EuvsCopyPort
) -> corpus.SyncReport:
    return asyncio.run(
        corpus.run_euvsdisinfo_sync(
            {"EUVSDISINFO_MCP_API_KEY": TOKEN},
            store,
            build_embeddings(EmbeddingsSettings()),
            now=NOW,
            http_client=server.client(),
        )
    )


def by_key(store: corpus.EuvsCopyPort) -> dict[str, corpus.StoredEntry]:
    return {s.entry.key: s for s in asyncio.run(store.entries())}


def test_second_run_without_changes_writes_nothing() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=12, articles=3)
    assert sync(server, store) == corpus.SyncReport(added=15)
    assert sync(server, store) == corpus.SyncReport()


def test_changed_fact_replaces_the_entry_and_its_vector() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=12, articles=1)
    sync(server, store)
    before = by_key(store)["case:1"]
    server.change_cases(1)
    assert sync(server, store) == corpus.SyncReport(updated=1)
    after = by_key(store)["case:1"]
    assert after.entry.fact == "Fact 1: no evidence supports the claim. Updated."
    assert after.fact_vector != before.fact_vector


def test_case_back_in_the_source_is_restored() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=12, articles=1)
    sync(server, store)
    removed = server.remove_cases(1)
    assert sync(server, store) == corpus.SyncReport(deleted=1)
    server.restore_cases(removed)
    assert sync(server, store) == corpus.SyncReport(updated=1)
    assert all(s.deleted_at is None for s in by_key(store).values())


def test_fact_text_is_a_secondary_mcp_source() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=1, articles=1)
    sync(server, store)
    entries = by_key(store)
    source = entries["case:1"].source
    assert source is not None
    assert (source.via, source.publisher_id, source.tier) == (
        "mcp",
        "eeas-euvsdisinfo",
        "secondary",
    )
    assert source.published_at == datetime.fromtimestamp(1_700_000_001, UTC)
    assert entries["article:2"].source is None


def test_linked_domains_are_flagged_without_www() -> None:
    server = FakeEuvsDisinfoServer(TOKEN)
    store = corpus.build_euvsdisinfo_copy()
    server.seed(cases=3, articles=1)
    sync(server, store)
    assert asyncio.run(store.flagged_domains()) == {
        "fake-news-0.example": ("case:3",),
        "fake-news-1.example": ("case:1",),
        "fake-news-2.example": ("case:2",),
    }


def test_failed_page_writes_nothing() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=150, articles=1)
    server.fail_at_offset(100)
    with pytest.raises(corpus.EuvsDisinfoUnavailableError):
        sync(server, store)
    assert asyncio.run(store.entries()) == []


def test_sse_answers_are_read() -> None:
    server = FakeEuvsDisinfoServer(TOKEN, sse=True)
    server.seed(cases=2, articles=1)
    assert sync(server, corpus.build_euvsdisinfo_copy()) == corpus.SyncReport(added=3)


def test_rejected_token_is_unavailable() -> None:
    server = FakeEuvsDisinfoServer("other")
    client = corpus.build_euvsdisinfo_client(
        {"EUVSDISINFO_MCP_API_KEY": TOKEN}, server.client()
    )
    with pytest.raises(corpus.EuvsDisinfoUnavailableError):
        asyncio.run(client.cases(limit=100, offset=0))


def test_missing_token_is_not_a_client() -> None:
    with pytest.raises(corpus.MissingTokenError):
        corpus.build_euvsdisinfo_client({}, FakeEuvsDisinfoServer(TOKEN).client())
    assert corpus.missing_env({"EUVSDISINFO_MCP_API_KEY": TOKEN}) == []


def test_catalog_entry_is_ingested_through_mcp() -> None:
    entry = corpus.catalog_entry()
    assert (entry.ingest, entry.publisher_id, entry.tier) == (
        "mcp",
        "eeas-euvsdisinfo",
        "secondary",
    )


def test_page_seen_twice_counts_once() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=150, articles=1)
    server.add_cases_after_first_page(3)
    # The 3 repeat on page 2; the new ones, before offset 0, wait for the next run.
    assert sync(server, store) == corpus.SyncReport(added=151)
    assert len(asyncio.run(store.entries())) == 151


def test_sse_event_split_over_lines_is_read() -> None:
    server = FakeEuvsDisinfoServer(TOKEN, sse=True, split_data=True)
    server.seed(cases=2, articles=1)
    assert sync(server, corpus.build_euvsdisinfo_copy()) == corpus.SyncReport(added=3)


def test_case_without_id_is_unavailable() -> None:
    server = FakeEuvsDisinfoServer(TOKEN)
    server.seed(cases=1, articles=1)
    server.drop_field("id")
    with pytest.raises(corpus.EuvsDisinfoUnavailableError):
        sync(server, corpus.build_euvsdisinfo_copy())


def test_malformed_link_flags_no_domain() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=1, articles=1)
    server.patch_cases(linksToDisinformation=["http://[::1", "https://ok.example/a"])
    assert sync(server, store) == corpus.SyncReport(added=2)
    assert asyncio.run(store.flagged_domains()) == {"ok.example": ("case:1",)}


def test_case_date_out_of_range_is_unavailable() -> None:
    server = FakeEuvsDisinfoServer(TOKEN)
    server.seed(cases=1, articles=1)
    server.patch_cases(date=10**20)
    with pytest.raises(corpus.EuvsDisinfoUnavailableError):
        sync(server, corpus.build_euvsdisinfo_copy())


def test_server_ignoring_offset_stops_after_max_pages() -> None:
    server = FakeEuvsDisinfoServer(TOKEN)
    server.seed(cases=100, articles=1)
    server.ignore_offset()
    with pytest.raises(corpus.EuvsDisinfoUnavailableError):
        sync(server, corpus.build_euvsdisinfo_copy())
    assert len(server.calls) == MAX_PAGES


def test_empty_cases_scan_leaves_the_copy() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=12, articles=3)
    sync(server, store)
    server.remove_cases(12, keep_oldest=0)
    with pytest.raises(corpus.EuvsDisinfoUnavailableError):
        sync(server, store)
    assert all(s.deleted_at is None for s in asyncio.run(store.entries()))
    assert asyncio.run(store.flagged_domains()) != {}


def test_sync_keeps_the_organiser_incidents() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=2, articles=1)
    incident = corpus.organiser.OrganiserIncident.model_validate(
        {
            "id": "x",
            "title": "T",
            "description": "D",
            "date": "2026-11-20",
            "license": "CC BY 4.0",
            "topics": "a",
        }
    )
    asyncio.run(
        corpus.organiser.import_incidents(
            [incident], store, build_embeddings(EmbeddingsSettings())
        )
    )
    assert sync(server, store).deleted == 0
    assert by_key(store)["organiser:x"].deleted_at is None
