"""Steps of corpus_ready.feature: the gold build on the in-memory store, no database."""

import asyncio
import os

from behave import given, then, when
from behave.runner import Context
from meritum_core.corpus.fakes import InMemoryLegalActMeta
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker.corpus.ready import (
    BronzeDocument,
    ReadyDeps,
    build_enabled,
    build_ready_layer,
)
from meritum_worker.corpus.ready.fakes import MemoryReadyStore

_HEADER = (
    "Konstytucja Rzeczypospolitej Polskiej z dnia 2 kwietnia 1997 r.\n\n"
    "Ustawa, ELI: DU/1997/483, Dz.U. 1997 nr 78 poz. 483, status: obowiązujący, "
    "w mocy od 1997-10-17, ogłoszono 1997-04-02."
)
_BODY = (
    "Rozdział I\nRZECZPOSPOLITA\n\n"
    "Art. 28. 1. Znakiem Rzeczypospolitej Polskiej jest wizerunek orła białego.\n\n"
    "Art. 29. Stolicą Rzeczypospolitej Polskiej jest Warszawa."
)


@given("dokument bronze Konstytucji z ELI DU/1997/483 w korpusie")
def step_constitution(context: Context) -> None:
    context.doc = BronzeDocument(
        source_id="konstytucja",
        url="https://api.sejm.gov.pl/eli/acts/DU/1997/483",
        domain="api.sejm.gov.pl",
        checksum="c" * 64,
        full_text=f"{_HEADER}\n\n{_BODY}",
        published_on=None,
    )
    context.store = MemoryReadyStore([context.doc])


@when("workflow corpus_ready_build buduje warstwę gold")
def step_build(context: Context) -> None:
    deps = ReadyDeps(
        store=context.store,
        legal_meta=InMemoryLegalActMeta(),
        embeddings=build_embeddings(EmbeddingsSettings(provider="stub")),
        catalog_kinds={"api.sejm.gov.pl": "akt_prawny"},
    )
    asyncio.run(build_ready_layer(deps, build_id="behave"))


@then('jest fragment "{label}" z nagłówkiem zawierającym "{address}" i rodzaj "{kind}"')
def step_chunk(context: Context, label: str, address: str, kind: str) -> None:
    chunks = [c for c, _ in context.store.gold["konstytucja"]]
    context.chunk = next(c for c in chunks if c.text.startswith(label))
    assert address in context.chunk.header, context.chunk.header
    assert context.chunk.kind.value == kind


@then(
    "tekst fragmentu jest równy znakom full_text bronze od start_offset do end_offset"
)
def step_offsets(context: Context) -> None:
    chunk = context.chunk
    assert context.doc.full_text[chunk.start_offset : chunk.end_offset] == chunk.text


@given("MERITUM_CORPUS_READY nie jest ustawione")
def step_flag_off(context: Context) -> None:
    context.saved = {k: os.environ.pop(k, None) for k in ("MERITUM_CORPUS_READY",)}
    os.environ["MERITUM_CORPUS_INGEST"] = "enabled"


@when("worker startuje")
def step_start(context: Context) -> None:
    context.scheduled = build_enabled()
    os.environ.pop("MERITUM_CORPUS_INGEST")
    for key, value in context.saved.items():
        if value is not None:
            os.environ[key] = value


@then("workflow corpus_ready_build nie jest zaplanowany")
def step_not_scheduled(context: Context) -> None:
    assert context.scheduled is False
