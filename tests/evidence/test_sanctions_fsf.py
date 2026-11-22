import asyncio
from datetime import date
from pathlib import Path

import pytest

from meritum_worker.evidence import (
    load_sanctions,
    parse_fsf_export,
    refresh_sanctions,
)

SAMPLE = Path(__file__).parent / "fixtures" / "fsf_export_sample.xml"
DAY = date(2026, 11, 22)


def test_the_official_export_gives_entities_with_their_domains() -> None:
    listed = {e.entity: e for e in parse_fsf_export(SAMPLE.read_bytes()).entities}

    parchin = listed["Parchin Chemical Industries (PCI)"]
    assert parchin.domains == ("icig.ir",)
    assert parchin.listed_on == date(2008, 6, 23)
    assert str(parchin.basis_url) == (
        "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202402074"
    )
    niru = listed["Niru Battery Manufacturing (Batrisazi-ye Niru)"]
    assert niru.domains == ("nirubattery.com", "niruco.com")


def test_an_entity_without_a_website_is_left_out() -> None:
    names = [e.entity for e in parse_fsf_export(SAMPLE.read_bytes()).entities]
    assert "Saddam Hussein Al-Tikriti" not in names


def test_a_page_on_a_shared_platform_does_not_list_the_platform() -> None:
    sanctions = parse_fsf_export(SAMPLE.read_bytes())
    assert "Oplot battalion" not in [e.entity for e in sanctions.entities]
    assert sanctions.warning_for("https://vk.com/some_user", on=DAY) is None


def test_a_value_with_a_stray_word_adds_no_guessed_domain() -> None:
    beget = next(
        e for e in parse_fsf_export(SAMPLE.read_bytes()).entities if "Beget" in e.entity
    )
    assert "kz.com" not in beget.domains
    assert {"beget.com", "beget.ru", "beget.de"} <= set(beget.domains)


def test_a_link_to_a_listed_domain_gets_the_warning() -> None:
    sanctions = parse_fsf_export(SAMPLE.read_bytes())
    warning = sanctions.warning_for("https://www.icig.ir/news/1", on=DAY)
    assert warning is not None
    assert warning.entity == "Parchin Chemical Industries (PCI)"


def test_refresh_stores_the_official_export_as_the_local_copy(tmp_path: Path) -> None:
    path = tmp_path / "sanctions.json"

    async def download() -> bytes:
        await asyncio.sleep(0)
        return SAMPLE.read_bytes()

    count = asyncio.run(refresh_sanctions(download, path))
    assert count == len(load_sanctions(path).entities) == 3


def test_an_export_without_any_website_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "sanctions.json"
    path.write_text('{"entities": []}')
    empty = b'<export xmlns="http://eu.europa.ec/fpi/fsd/export"></export>'

    async def download() -> bytes:
        await asyncio.sleep(0)
        return empty

    with pytest.raises(ValueError, match="no entity"):
        asyncio.run(refresh_sanctions(download, path))
    assert path.read_text() == '{"entities": []}'


def test_an_export_with_a_doctype_is_refused() -> None:
    hostile = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><export/>'
    with pytest.raises(ValueError, match="not a valid FSF export"):
        parse_fsf_export(hostile)
