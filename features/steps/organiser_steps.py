"""Steps for the organiser's import in features/corpus.feature, on a generated file."""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus

ENV = {"MERITUM_CORPUS_INGEST": "enabled"}
LICENSED = 2  # of the three entries, the one without a licence is skipped


def incident(number: int) -> dict[str, object]:
    return {
        "id": f"inc-{number}",
        "title": f"Incydent {number}",
        "description": f"Fałszywa informacja numer {number}",
        "date": "2026-11-20",
        "license": "CC BY 4.0",
        "topics": ["bezpieczeństwo"],
    }


def write_file(context: Context, records: list[dict[str, object]]) -> None:
    folder = Path(tempfile.mkdtemp())
    context.add_cleanup(shutil.rmtree, folder)
    context.path = folder / "organiser_incidents.json"
    context.path.write_text(json.dumps({"incidents": records}), "utf-8")
    context.store = corpus.build_euvsdisinfo_copy()


def run_import(context: Context) -> corpus.ImportReport:
    return asyncio.run(
        corpus.import_organiser_file(
            context.path,
            corpus.build_organiser_file(),
            context.store,
            build_embeddings(EmbeddingsSettings()),
            env=ENV,
        )
    )


@given(
    "plik bazy incydentów od organizatora z {count:d} wpisami"
    " z datą, licencją i zakresem tematycznym"
)
def incident_file(context: Context, count: int) -> None:
    write_file(context, [incident(n) for n in range(1, count + 1)])


@given("wpis bez pola licencji")
def unlicensed(context: Context) -> None:
    records = [incident(n) for n in range(1, 4)]
    del records[1]["license"]
    write_file(context, records)


@when("workflow importu kończy przebieg")
@when("workflow importu go czyta")
def import_finishes(context: Context) -> None:
    context.report = run_import(context)


@then(
    '{count:d} incydentów jest w korpusie z database "{database}",'
    " z embeddingami wielojęzycznymi opisu"
)
def incidents_stored(context: Context, count: int, database: str) -> None:
    stored = asyncio.run(context.store.entries())
    assert len(stored) == count, len(stored)
    assert all(s.entry.database == database for s in stored)
    assert all(s.description_vector for s in stored)


@then("ponowny import tego samego pliku niczego nie duplikuje")
def import_again(context: Context) -> None:
    before = len(asyncio.run(context.store.entries()))
    report = run_import(context)
    assert (report.added, report.updated) == (0, 0), report
    assert len(asyncio.run(context.store.entries())) == before


@then("wpis jest pominięty z zapisanym powodem, a pozostałe są zaimportowane")
def skipped_with_reason(context: Context) -> None:
    skipped = context.report.skipped
    assert [(s.id, s.reason) for s in skipped] == [("inc-2", "missing_license")]
    assert context.report.added == LICENSED
