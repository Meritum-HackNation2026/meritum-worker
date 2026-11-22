"""The public bundle: cases, sources, manifest; never full texts or cassettes."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from meritum_core.corpus.fetching import FetchedPage, FetchFailureReason

from meritum_worker.observability import (
    Cassette,
    Manifest,
    PageTake,
    meritum_eval_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "evals" / "golden" / "cases.json"
TEXT = "Pełny tekst strony, który zostaje w kasecie i nigdy nie trafia do paczki."
AT = datetime(2026, 11, 20, 9, tzinfo=UTC)


def _cassette(path: Path) -> Path:
    page = FetchedPage(
        url="https://example.org/final", content_type="text/html", untrusted_text=TEXT
    )
    cassette = Cassette(corpus_version="2026-11-20T10:00Z")
    cassette.pages["read"] = [
        PageTake(reason=FetchFailureReason.TIMEOUT, fetched_at=AT),
        PageTake(page=page, fetched_at=AT),
    ]
    cassette.pages["failed"] = [
        PageTake(reason=FetchFailureReason.NOT_FOUND, fetched_at=AT)
    ]
    cassette.save(path / "cassette.json")
    return path / "cassette.json"


def _bundle(tmp_path: Path) -> Path:
    out = tmp_path / "bundle"
    meritum_eval_bundle([
        "--cases", str(GOLDEN), "--cassette", str(_cassette(tmp_path)),
        "--output", str(out),
    ])  # fmt: skip
    return out


def test_bundle_has_no_full_text_and_no_cassette(tmp_path: Path) -> None:
    out = _bundle(tmp_path)
    names = sorted(path.name for path in out.iterdir())
    assert names == ["cases.json", "manifest.json", "sources.json"]
    for path in out.iterdir():
        content = path.read_text(encoding="utf-8")
        assert TEXT not in content
        assert "untrusted_text" not in content


def test_manifest_lists_read_pages_with_checksum_and_fetch_time(tmp_path: Path) -> None:
    path = _bundle(tmp_path) / "manifest.json"
    assert Manifest.model_validate_json(path.read_text()).documents[0].document_id
    manifest = json.loads(path.read_text())
    assert manifest == {
        "corpus_version": "2026-11-20T10:00Z",
        "documents": [
            {
                "document_id": "read",
                "url": "https://example.org/final",
                "sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
                "fetched_at": "2026-11-20T09:00:00Z",
            }
        ],
    }


def test_sources_keep_address_and_quote_of_every_case(tmp_path: Path) -> None:
    sources = json.loads((_bundle(tmp_path) / "sources.json").read_text())
    golden = json.loads(GOLDEN.read_text())
    expected = sum(len(case.get("sources", [])) for case in golden)
    assert len(sources) == expected
    assert {"case_id", "url", "publisher", "quote"} == set(sources[0])


def test_cassette_inside_the_bundle_folder_is_refused(tmp_path: Path) -> None:
    cassette = _cassette(tmp_path)
    with pytest.raises(SystemExit):
        meritum_eval_bundle(
            [
                "--cases",
                str(GOLDEN),
                "--cassette",
                str(cassette),
                "--output",
                str(tmp_path),
            ]
        )
    assert not (tmp_path / "manifest.json").exists()
