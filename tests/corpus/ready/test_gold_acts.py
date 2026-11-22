"""Gold chunks of a legal act built from the real ELI record and act_body format."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus import LegalActMeta
from meritum_core.corpus.ready import STUB_WEIGHT, DocumentKind

from meritum_worker.corpus.catalog_api import (
    act_body,
    act_parts,
    api_listings,
    parse_listing,
)
from meritum_worker.corpus.ready import BronzeDocument, gold_chunks

FIXTURES = Path(__file__).parents[1] / "fixtures" / "api"
NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
ART_29 = "Art. 29. Stolicą Rzeczypospolitej Polskiej jest Warszawa."
SEJM = CatalogEntry.model_validate(
    {
        "domain": "api.sejm.gov.pl",
        "publisher": "Kancelaria Sejmu",
        "publisher_id": "kancelaria-sejmu",
        "kind": "akt_prawny",
        "tier": "primary",
        "license": "materiał urzędowy",
        "ingest": "api",
        "qualified_because": "Oficjalne API ELI.",
    }
)


def constitution(
    pdf_text: str, answer: dict[str, object] | None = None
) -> BronzeDocument:
    raw = json.loads(
        (FIXTURES / "sejm-eli-du-1997-483.json").read_text(encoding="utf-8")
    )
    (listing,) = [
        x
        for x in api_listings(SEJM, NOW, legal_acts=("DU/1997/483",))
        if x.url.endswith("DU/1997/483")
    ]
    (record,) = parse_listing(listing, json.dumps(raw | (answer or {})))
    parts = act_parts(record, act_body(pdf_text)) if pdf_text else [record]
    return BronzeDocument(
        source_id="k",
        url=parts[0].url,
        domain="api.sejm.gov.pl",
        checksum="c" * 64,
        full_text=parts[0].text,
        published_on=date(1997, 4, 2),
    )


def test_constitution_gets_one_chunk_per_article_with_the_act_header() -> None:
    doc = constitution(
        "Rozdział I\r\nRZECZPOSPOLITA\r\nArt. 28. 1. Znakiem jest orzeł.\r\n" + ART_29
    )

    chunks = gold_chunks(doc, "akt_prawny", None)

    art29 = next(c for c in chunks if c.text == ART_29)
    assert doc.full_text[art29.start_offset : art29.end_offset] == ART_29
    assert "Dz.U. 1997 nr 78 poz. 483" in art29.header
    assert "Rozdział I RZECZPOSPOLITA" in art29.header
    assert art29.kind is DocumentKind.ACT
    assert art29.eli == "DU/1997/483"
    assert art29.valid_from == date(1997, 10, 17)
    assert [c.text[:8] for c in chunks] == ["Art. 28.", "Art. 29."]


def test_long_article_is_split_by_subsection_and_continuations_name_it() -> None:
    long = "Art. 96. " + "\r\n".join(f"{i}. " + "słowo " * 60 for i in range(1, 8))
    doc = constitution(long)

    chunks = gold_chunks(doc, "akt_prawny", None)

    assert len(chunks) > 1
    assert all(len(c.text) <= 1200 for c in chunks)
    assert chunks[1].header.endswith("Art. 96. (cd.)")
    assert all(doc.full_text[c.start_offset : c.end_offset] == c.text for c in chunks)


def test_title_only_act_is_one_low_weight_chunk() -> None:
    chunks = gold_chunks(constitution(""), "akt_prawny", None)

    assert len(chunks) == 1
    assert chunks[0].weight == STUB_WEIGHT


def test_stored_act_metadata_wins_over_the_header_text() -> None:
    meta = LegalActMeta(
        eli="DU/2025/1242",
        document_type="Rozporządzenie",
        legal_status="wygaśnięcie aktu",
        in_force=False,
        in_force_from=date(2025, 1, 1),
        in_force_until=date(2025, 12, 31),
        journal_publisher="DU",
        journal_year=2025,
        journal_position=1242,
        display_address="Dz.U. 2025 poz. 1242",
    )

    (chunk,) = gold_chunks(constitution(ART_29), "akt_prawny", meta)

    assert chunk.valid_to == date(2025, 12, 31)
    assert "Dz.U. 2025 poz. 1242" in chunk.header
