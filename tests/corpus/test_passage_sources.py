import asyncio
from datetime import UTC, date, datetime

from meritum_core.corpus import Passage, RankedPassage
from meritum_core.corpus.catalog import load_catalog

from meritum_worker.checks import FakeCorpusDocuments
from meritum_worker.corpus import DocumentMeta, passage_documents

FETCHED_AT = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
CATALOG = load_catalog()


def _meta(source_id: str, domain: str = "www.gov.pl/web/rcb") -> DocumentMeta:
    return DocumentMeta(
        source_id=source_id,
        url=f"https://{domain}/{source_id}",
        domain=domain,
        publisher_id="rcb",
        license="public",
        published_on=date(2026, 11, 19),
        fetched_at=FETCHED_AT,
        checksum="0" * 64,
    )


def _ranked(source_id: str, passage_id: str, text: str) -> RankedPassage:
    passage = Passage(
        passage_id=passage_id,
        source_id=source_id,
        text=text,
        published_on=date(2026, 11, 19),
        fetched_at=FETCHED_AT,
    )
    return RankedPassage(passage=passage, relevance=0.8)


def test_passages_of_one_document_make_one_source_with_catalogue_metadata() -> None:
    texts = ("RCB ostrzega przed burzami na Mazowszu.", "Obowiązuje do niedzieli.")
    first = _ranked("doc-a", "a1", texts[0])
    second = _ranked("doc-a", "a2", texts[1])
    passages = {"burze": [first, second], "niedziela": [second]}

    found = asyncio.run(
        passage_documents(passages, FakeCorpusDocuments([_meta("doc-a")]), CATALOG)
    )

    burze, niedziela = found["burze"], found["niedziela"]
    assert burze == niedziela
    [document] = burze
    assert document.text == f"{texts[0]}\n\n{texts[1]}"
    source = document.source
    assert (source.id, str(source.url)) == ("doc-a", "https://www.gov.pl/web/rcb/doc-a")
    assert (source.publisher, source.publisher_id, source.domain) == (
        "Rządowe Centrum Bezpieczeństwa",
        "rcb",
        "www.gov.pl/web/rcb",
    )
    assert (source.tier, source.via, source.language) == ("primary", "corpus", "pl")
    assert source.published_at == datetime(2026, 11, 19, tzinfo=UTC)
    assert source.fetched_at == FETCHED_AT


def test_source_keeps_the_way_its_document_came_into_the_corpus() -> None:
    meta = _meta("doc-a").model_copy(update={"via": "rss"})
    passages = {"burze": [_ranked("doc-a", "a1", "RCB ostrzega przed burzami.")]}

    found = asyncio.run(
        passage_documents(passages, FakeCorpusDocuments([meta]), CATALOG)
    )

    assert found["burze"][0].source.via == "rss"


def test_passage_without_document_or_catalogue_entry_is_left_out() -> None:
    passages = {
        "burze": [
            _ranked("doc-gone", "g1", "Dokument zniknął z korpusu."),
            _ranked("doc-out", "o1", "Domena wypadła z katalogu."),
            _ranked("doc-a", "a1", "RCB ostrzega przed burzami."),
        ]
    }
    documents = FakeCorpusDocuments(
        [_meta("doc-a"), _meta("doc-out", domain="example.com")]
    )

    found = asyncio.run(passage_documents(passages, documents, CATALOG))

    assert [d.source.id for d in found["burze"]] == ["doc-a"]
