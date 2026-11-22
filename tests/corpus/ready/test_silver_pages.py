"""Silver cleaning, page and excerpt chunks, and number tags."""

from datetime import date

from meritum_core.corpus.ready import NumberTag

from meritum_worker.corpus.ready import BronzeDocument, clean, gold_chunks, number_tags

MENU = "Start\nAktualności\nKontakt\nSzukaj"
ARTICLE = "Minister ogłosił, że płaca minimalna w 2026 r. wyniesie 4806 zł brutto."


def doc(text: str, domain: str = "www.gov.pl/web/rodzina") -> BronzeDocument:
    return BronzeDocument(
        source_id="s",
        url="https://x",
        domain=domain,
        checksum="c" * 64,
        full_text=text,
        published_on=date(2026, 9, 15),
    )


def test_silver_drops_menus_footers_and_repeats_and_keeps_offsets() -> None:
    text = f"{MENU}\n\n{ARTICLE}\n\nPliki cookies\n\n{ARTICLE}"

    spans = clean(text)

    assert [text[s.start : s.end] for s in spans] == [ARTICLE]


def test_page_is_chunked_by_heading_and_the_heading_is_in_the_header() -> None:
    text = f"Płaca minimalna 2026\n\n{MENU}\n\nNowe stawki\n\n{ARTICLE}"

    (chunk,) = gold_chunks(doc(text), "instytucja", None)

    assert chunk.text == ARTICLE
    assert chunk.header.startswith(
        "Płaca minimalna 2026 (www.gov.pl/web/rodzina, 2026-09-15)."
    )
    assert chunk.header.endswith("Nowe stawki.")
    assert chunk.subject == "rodzina"
    assert chunk.numbers == (NumberTag(value="4806", unit="zł", period="2026"),)


def test_fact_checker_gets_one_short_excerpt_only() -> None:
    text = "Ocena. " + "zdanie " * 100 + "\n\nDruga część."

    chunks = gold_chunks(doc(text, "demagog.org.pl"), "fact_check", None)

    assert len(chunks) == 1
    assert len(chunks[0].text) <= 300
    assert text.startswith(chunks[0].text)


def test_number_tags_read_percent_and_year() -> None:
    assert number_tags("Stawka VAT w 2026 r. wynosi 23 %.") == (
        NumberTag(value="23", unit="%", period="2026"),
    )
