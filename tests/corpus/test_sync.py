"""The EUvsDisinfo sync writes a difference; tested on the fake MCP server."""

import asyncio
from datetime import UTC, datetime

import pytest
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.fakes import FakeEuvsDisinfoServer

TOKEN = "token"  # ruff: ignore[hardcoded-password-string]  # the fake server's token
NOW = datetime(2026, 11, 21, tzinfo=UTC)


def sync(
    server: FakeEuvsDisinfoServer, store: corpus.EuvsCopyPort
) -> corpus.SyncReport:
    client = corpus.build_euvsdisinfo_client(
        {"EUVSDISINFO_MCP_API_KEY": TOKEN}, http_client=server.client()
    )
    embeddings = build_embeddings(EmbeddingsSettings())
    return asyncio.run(corpus.sync_euvsdisinfo(client, store, embeddings, now=NOW))


def by_key(store: corpus.EuvsCopyPort) -> dict[str, corpus.StoredEntry]:
    return {s.entry.key: s for s in asyncio.run(store.entries())}


def test_second_run_without_changes_writes_nothing() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=12, articles=3)
    assert sync(server, store) == corpus.SyncReport(added=15)
    assert sync(server, store) == corpus.SyncReport()


def test_changed_fact_replaces_the_entry_and_its_vector() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=12, articles=0)
    sync(server, store)
    before = by_key(store)["case:1"]
    server.change_cases(1)
    assert sync(server, store) == corpus.SyncReport(updated=1)
    after = by_key(store)["case:1"]
    assert after.entry.fact == "Fact 1: no evidence supports the claim. Updated."
    assert after.fact_vector != before.fact_vector


def test_case_back_in_the_source_is_restored() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=12, articles=0)
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
    server.seed(cases=3, articles=0)
    sync(server, store)
    assert store.flagged_domains == {  # ty: ignore[missing-attribute]  # memory copy
        "fake-news-0.example": ("case:3",),
        "fake-news-1.example": ("case:1",),
        "fake-news-2.example": ("case:2",),
    }


def test_failed_page_writes_nothing() -> None:
    server, store = FakeEuvsDisinfoServer(TOKEN), corpus.build_euvsdisinfo_copy()
    server.seed(cases=150, articles=0)
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
        {"EUVSDISINFO_MCP_API_KEY": TOKEN}, http_client=server.client()
    )
    with pytest.raises(corpus.EuvsDisinfoUnavailableError):
        asyncio.run(client.cases(limit=100, offset=0))


def test_missing_token_is_not_a_client() -> None:
    with pytest.raises(corpus.MissingTokenError):
        corpus.build_euvsdisinfo_client({})
    assert corpus.missing_env({"EUVSDISINFO_MCP_API_KEY": TOKEN}) == []


def test_catalog_entry_is_ingested_through_mcp() -> None:
    entry = corpus.catalog_entry()
    assert (entry.ingest, entry.publisher_id, entry.tier) == (
        "mcp",
        "eeas-euvsdisinfo",
        "secondary",
    )
