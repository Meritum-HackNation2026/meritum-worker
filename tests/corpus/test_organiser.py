"""The organiser's files: validation, the file adapter and an idempotent import."""

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus import organiser

FIXTURES = Path(__file__).parent / "fixtures"
INCIDENTS = FIXTURES / "organiser_incidents.csv"
ENABLED = {"MERITUM_CORPUS_INGEST": "enabled"}
VALID = {
    "id": 7,
    "title": "Incydent",
    "description": "Opis",
    "date": "2026-11-20",
    "license": "CC BY 4.0",
    "topics": "zdrowie; wybory",
}


def run(
    path: Path, store: corpus.EuvsCopyPort, env: dict[str, str] = ENABLED
) -> corpus.ImportReport:
    return asyncio.run(
        corpus.import_organiser_file(
            path,
            corpus.build_organiser_file(),
            store,
            build_embeddings(EmbeddingsSettings()),
            env=env,
        )
    )


def test_csv_topics_split_and_bare_date_is_midnight_utc() -> None:
    incident = organiser.OrganiserIncident.model_validate(VALID)
    assert incident.id == "7"
    assert incident.topics == ("zdrowie", "wybory")
    assert incident.date == date(2026, 11, 20)
    assert incident.published_at() == datetime(2026, 11, 20, tzinfo=UTC)


@pytest.mark.parametrize(
    ("drop", "reason"),
    [("license", "missing_license"), ("description", "invalid_record")],
)
def test_bad_record_is_skipped_with_its_reason(drop: str, reason: str) -> None:
    record = {k: v for k, v in VALID.items() if k != drop}
    valid, skipped = organiser.validated([record, VALID], organiser.OrganiserIncident)
    assert len(valid) == 1
    assert skipped == [organiser.SkippedRecord(id="7", reason=reason, detail=drop)]


def test_import_stores_licence_retention_and_skips_unlicensed() -> None:
    store = corpus.build_euvsdisinfo_copy()
    report = run(INCIDENTS, store)
    assert (report.added, [s.id for s in report.skipped]) == (2, ["inc-3"])
    stored = {s.entry.key: s.entry for s in asyncio.run(store.entries())}
    first = stored["organiser:inc-1"]
    assert (first.database, first.kind, first.license) == (
        "organiser",
        "case",
        "CC BY 4.0",
    )
    assert (first.retention_days, first.topics) == (365, ("zdrowie", "bezpieczeństwo"))


def test_second_import_changes_nothing() -> None:
    store = corpus.build_euvsdisinfo_copy()
    run(INCIDENTS, store)
    report = run(INCIDENTS, store)
    assert (report.added, report.updated, report.unchanged) == (0, 0, 2)
    assert len(asyncio.run(store.entries())) == 2


def test_import_is_off_where_corpus_is_not_writable() -> None:
    store = corpus.build_euvsdisinfo_copy()
    assert run(INCIDENTS, store, env={}) == corpus.ImportReport(disabled=True)
    assert asyncio.run(store.entries()) == []


def test_json_source_list_is_validated(tmp_path: Path) -> None:
    sources = tmp_path / "organiser_sources.json"
    record = {
        "id": "s1",
        "name": "RCB",
        "url": "https://gov.pl/rcb",
        "date": "2026-11-20",
        "license": "public",
        "topics": ["bezpieczeństwo"],
    }
    sources.write_text(json.dumps({"sources": [record, {"id": "s2"}]}), "utf-8")
    report = run(sources, corpus.build_euvsdisinfo_copy())
    assert (report.sources, [s.id for s in report.skipped]) == (1, ["s2"])


def test_other_extension_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "incidents.xlsx"
    path.write_text("", "utf-8")
    with pytest.raises(ValueError, match=r"expected \.json or \.csv"):
        run(path, corpus.build_euvsdisinfo_copy())
