import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from meritum_core.checks.contracts import CatalogEntry
from pydantic import ValidationError

from meritum_worker.corpus.catalog_api import (
    ApiListing,
    LegalActsSettings,
    act_body,
    act_parts,
    act_units,
    api_listings,
    parse_listing,
)

NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "api"
ACTS = "https://api.sejm.gov.pl/eli/acts"
CONSTITUTION = f"{ACTS}/DU/1997/483"
CONSTITUTION_PDF = f"{CONSTITUTION}/text/U/D19970483Lj.pdf"
MINIMUM_WAGE = f"{ACTS}/DU/2025/1242"
ARTICLE_29 = "Art. 29. Stolicą Rzeczypospolitej Polskiej jest Warszawa."


def sejm() -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": "api.sejm.gov.pl",
            "publisher": "Kancelaria Sejmu",
            "publisher_id": "kancelaria-sejmu",
            "kind": "akt_prawny",
            "tier": "primary",
            "license": "materiał urzędowy (akty normatywne)",
            "ingest": "api",
            "qualified_because": "Oficjalne API ELI.",
        }
    )


def recorded(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def act_listing(eli: str) -> ApiListing:
    (listing,) = [
        listing
        for listing in api_listings(sejm(), NOW, legal_acts=(eli,))
        if listing.url == f"{ACTS}/{eli}"
    ]
    return listing


def test_configured_acts_are_listed_before_the_year() -> None:
    listings = api_listings(sejm(), NOW, legal_acts=("DU/1997/483", "MP/2026/202"))
    assert [listing.url for listing in listings] == [
        CONSTITUTION,
        f"{ACTS}/MP/2026/202",
        f"{ACTS}/DU/2026",
    ]


def test_act_record_has_metadata_and_prefers_the_consolidated_pdf() -> None:
    (record,) = parse_listing(
        act_listing("DU/1997/483"), recorded("sejm-eli-du-1997-483.json")
    )
    assert record.url == CONSTITUTION
    assert record.text_url == CONSTITUTION_PDF
    assert record.published_at == date(1997, 4, 2)
    assert "Konstytucja Rzeczypospolitej Polskiej z dnia 2 kwietnia 1997 r." in (
        record.text
    )
    assert "ELI: DU/1997/483, Dz.U. 1997 nr 78 poz. 483" in record.text
    assert "status: obowiązujący" in record.text
    assert "w mocy od 1997-10-17" in record.text


def test_act_without_a_consolidated_text_reads_text_pdf() -> None:
    (record,) = parse_listing(
        act_listing("DU/2025/1242"), recorded("sejm-eli-du-2025-1242.json")
    )
    assert record.text_url == f"{MINIMUM_WAGE}/text.pdf"
    assert record.published_at == date(2025, 9, 15)


def test_act_without_any_text_wants_it_but_has_no_url() -> None:
    answer = json.loads(recorded("sejm-eli-du-2025-1242.json"))
    answer |= {"textPDF": False, "textHTML": False, "texts": []}
    (record,) = parse_listing(act_listing("DU/2025/1242"), json.dumps(answer))
    assert record.wants_text
    assert record.text_url is None


def test_act_body_drops_page_headers_and_starts_each_article_a_paragraph() -> None:
    first = (
        "©Kancelaria Sejmu s. 1/56\r\n2015-01-07\r\nRozdział I\r\nRZECZPOSPOLITA\r\n"
        "Art. 1. Rzeczpospolita Polska jest dobrem\r\nwspólnym.\r\n"
        "Art. 2. Pro\x02wadzi."
    )
    pages = [first, "Dziennik Ustaw \u2013 2 \u2013 Poz. 592\r\nArt. 3. Dalej."]
    assert act_body("\f".join(pages)) == (
        "Rozdział I\nRZECZPOSPOLITA\n\n"
        "Art. 1. Rzeczpospolita Polska jest dobrem\nwspólnym.\n\n"
        "Art. 2. Prowadzi.\n\nArt. 3. Dalej."
    )


def test_long_act_is_split_into_parts_with_the_metadata_in_each() -> None:
    (record,) = parse_listing(
        act_listing("DU/1997/483"), recorded("sejm-eli-du-1997-483.json")
    )
    body = "\n\n".join(f"Art. {i}. " + "słowo " * 200 for i in range(1, 300))
    parts = act_parts(record, body)
    assert len(parts) > 1
    assert parts[0].url == CONSTITUTION
    assert parts[1].url == f"{CONSTITUTION}#czesc-2"
    assert all(part.text.startswith(record.text) for part in parts)
    assert all(len(part.text) <= 60_000 + len(record.text) + 100 for part in parts)
    assert "Art. 299." in parts[-1].text


def test_settings_list_acts_by_eli() -> None:
    assert "DU/1997/483" in LegalActsSettings().acts
    assert LegalActsSettings(acts=("MP/2026/202",)).acts == ("MP/2026/202",)
    with pytest.raises(ValidationError):
        LegalActsSettings(acts=("../etc/passwd",))


def test_consolidated_texts_in_force_come_from_the_search() -> None:
    listings = api_listings(sejm(), NOW, search_limit=3)
    search = listings[-2]
    assert search.url.startswith(f"{ACTS}/search?publisher=DU&type=Obwieszczenie")
    assert "inForce=1" in search.url
    assert search.url.endswith("limit=3")
    records = parse_listing(search, recorded("sejm-eli-search-tj.json"))
    assert len(records) == 3
    assert all(r.wants_text for r in records)
    assert records[0].text_url == f"{ACTS}/DU/2025/1226/text/U/D20251226Lj.pdf"


def test_act_record_carries_its_eli_metadata() -> None:
    (record,) = parse_listing(
        act_listing("DU/1997/483"), recorded("sejm-eli-du-1997-483.json")
    )
    assert record.act is not None
    assert record.act.model_dump() == {
        "eli": "DU/1997/483",
        "title": "Konstytucja Rzeczypospolitej Polskiej z dnia 2 kwietnia 1997 r.",
        "document_type": "Ustawa",
        "legal_status": "obowiązujący",
        "in_force": True,
        "in_force_from": date(1997, 10, 17),
        "in_force_until": None,
        "journal_publisher": "DU",
        "journal_year": 1997,
        "journal_position": 483,
        "display_address": "Dz.U. 1997 nr 78 poz. 483",
        "published_on": date(1997, 4, 2),
    }


def test_expired_act_states_until_when_it_was_in_force() -> None:
    answer = json.loads(recorded("sejm-eli-du-2025-1242.json"))
    answer |= {"inForce": "NOT_IN_FORCE", "expirationDate": "2026-12-31"}
    (record,) = parse_listing(act_listing("DU/2025/1242"), json.dumps(answer))
    assert record.act is not None
    assert not record.act.in_force
    assert record.act.in_force_from == date(2026, 1, 1)
    assert record.act.in_force_until == date(2026, 12, 31)
    journal = (
        record.act.journal_publisher,
        record.act.journal_year,
        record.act.journal_position,
    )
    assert journal == ("DU", 2025, 1242)
    assert "w mocy od 2026-01-01 do 2026-12-31" in record.text


def test_act_units_split_articles_and_keep_their_labels() -> None:
    body = act_body(
        "Preambuła.\r\nRozdział I\r\nArt. 29. Stolicą Rzeczypospolitej Polskiej"
        " jest Warszawa.\r\nArt. 96. 1. Sejm składa się z 460 posłów.\r\n"
        "2. Wybory do Sejmu są powszechne.\r\n§ 1. Ustala się 4806 zł."
    )
    units = act_units(body)
    assert [u.label for u in units] == ["", "Rozdział", "Art. 29.", "Art. 96.", "§ 1."]
    assert units[3].text == (
        "Art. 96. 1. Sejm składa się z 460 posłów.\n2. Wybory do Sejmu są powszechne."
    )
