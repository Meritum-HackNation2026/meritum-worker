"""build_ready_layer over the in-memory store, and when the build is scheduled."""

import asyncio
from datetime import date

import pytest
from meritum_core.corpus.fakes import InMemoryLegalActMeta
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker.corpus.ready import (
    BronzeDocument,
    ReadyDeps,
    build_enabled,
    build_ready_layer,
)
from meritum_worker.corpus.ready.fakes import MemoryReadyStore

TEXT = "Komunikat\n\nWojewoda ogłosił stan pogotowia przeciwpowodziowego w gminie."


def doc(sid: str, checksum: str = "a" * 64) -> BronzeDocument:
    return BronzeDocument(
        source_id=sid,
        url=f"https://x/{sid}",
        domain="www.gov.pl/web/rcb",
        checksum=checksum,
        full_text=TEXT,
        published_on=date(2026, 11, 1),
    )


def deps(store: MemoryReadyStore) -> ReadyDeps:
    return ReadyDeps(
        store=store,
        legal_meta=InMemoryLegalActMeta(),
        embeddings=build_embeddings(EmbeddingsSettings(provider="stub")),
        catalog_kinds={"www.gov.pl/web/rcb": "instytucja"},
    )


def test_build_writes_silver_and_gold_then_skips_unchanged_documents() -> None:
    store = MemoryReadyStore([doc("a"), doc("b")])

    first = asyncio.run(build_ready_layer(deps(store), build_id="b1"))
    second = asyncio.run(build_ready_layer(deps(store), build_id="b2"))

    assert store.prepared
    assert (first.documents, first.chunks) == (2, 2)
    assert (second.documents, second.chunks) == (0, 0)
    chunk, vector = store.gold["a"][0]
    assert TEXT[chunk.start_offset : chunk.end_offset] == chunk.text
    assert len(vector) == 768


def test_changed_document_is_rebuilt_and_removed_one_forgotten() -> None:
    store = MemoryReadyStore([doc("a"), doc("b")])
    asyncio.run(build_ready_layer(deps(store), build_id="b1"))
    store.bronze = {"a": doc("a", "b" * 64)}

    report = asyncio.run(build_ready_layer(deps(store), build_id="b2"))

    assert (report.documents, report.removed) == (1, 1)
    assert set(store.gold) == {"a"}
    assert store.gold["a"][0][0].checksum == "b" * 64


@pytest.mark.parametrize(
    ("ready", "ingest", "expected"),
    [
        (None, "enabled", False),
        ("false", "enabled", False),
        ("true", "", False),
        ("true", "enabled", True),
    ],
)
def test_build_is_scheduled_only_with_the_flag_and_corpus_writes(
    monkeypatch: pytest.MonkeyPatch, ready: str | None, ingest: str, *, expected: bool
) -> None:
    if ready is None:
        monkeypatch.delenv("MERITUM_CORPUS_READY", raising=False)
    else:
        monkeypatch.setenv("MERITUM_CORPUS_READY", ready)
    monkeypatch.setenv("MERITUM_CORPUS_INGEST", ingest)

    assert build_enabled() is expected
