"""Corpus passages as source documents, with metadata from the corpus and catalogue.

A passage carries only its source id and dates. Link and domain come from the
document in the corpus, publisher, kind and tier from its catalogue entry; a
passage with neither stays out, so nothing is shown without its metadata.

Features:
    US-KOR-02, US-ZRD-01, F-12, F-16
"""

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time

from meritum_core.checks.contracts import CatalogEntry, Source
from meritum_core.corpus import RankedPassage
from meritum_core.evidence.models import SourceDocument

from meritum_worker.corpus.constants import WEB_TITLE_MAX_CHARS
from meritum_worker.corpus.documents import DocumentMeta
from meritum_worker.corpus.language import detect_language
from meritum_worker.corpus.passage_ports import CorpusDocumentsPort


async def passage_documents(
    passages: Mapping[str, Sequence[RankedPassage]],
    documents: CorpusDocumentsPort,
    catalog: Sequence[CatalogEntry],
) -> dict[str, list[SourceDocument]]:
    """Turn each fact's reranked passages into source documents.

    Passages of one document, whichever fact found them, make one document
    whose text joins them in reranking order, so a source id names one text.

    Args:
        passages: reranked passages per fact, keyed by the claim text.
        documents: the corpus documents the passages come from.
        catalog: the loaded catalogue.

    Returns:
        The documents per claim text, in reranking order; a passage whose
        document or catalogue entry is missing is left out.

    Features:
        US-KOR-02, US-ZRD-01, F-12, F-16
    """
    texts: dict[str, dict[str, str]] = {}
    for ranked in passages.values():
        for found in ranked:
            passage = found.passage
            texts.setdefault(passage.source_id, {})[passage.passage_id] = passage.text
    ids = list(texts)
    metas = await asyncio.gather(*map(documents.document, ids))
    entries = {entry.domain: entry for entry in catalog}
    # A blank line between passages: a fragment is checked within one of them.
    built = {
        source_id: _document(meta, entry, "\n\n".join(parts.values()))
        for source_id, meta, parts in zip(ids, metas, texts.values(), strict=True)
        if meta is not None and (entry := entries.get(meta.domain)) is not None
    }
    return {
        claim: [
            built[source_id]
            for source_id in dict.fromkeys(f.passage.source_id for f in ranked)
            if source_id in built
        ]
        for claim, ranked in passages.items()
    }


def _document(meta: DocumentMeta, entry: CatalogEntry, text: str) -> SourceDocument:
    published = meta.published_on
    source = Source(
        id=meta.source_id,
        # The corpus keeps no title; the address names the page, as in live search.
        title=meta.url[:WEB_TITLE_MAX_CHARS],
        publisher=entry.publisher,
        publisher_id=entry.publisher_id,
        url=meta.url,
        domain=entry.domain,
        kind=entry.kind,
        tier=entry.tier,
        published_at=None
        if published is None
        else datetime.combine(published, time(), UTC),
        fetched_at=meta.fetched_at,
        language=detect_language(text),
        via=meta.via,
        max_age_hours=entry.max_age_hours,
    )
    return SourceDocument(source=source, text=text)
