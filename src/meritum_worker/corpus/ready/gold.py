"""Gold: retrieval-ready chunks of one bronze document, before embedding.

Acts go per article (``acts``), official pages per heading, media and
fact-checkers get one short excerpt. Every chunk's text is a bronze span; tags
come from the text and metadata by rule, never from an LLM rewrite.

Features:
    US-KOR-02, US-ZRD-05, F-12
"""

import re
from collections.abc import Mapping

from meritum_core.corpus import LegalActMeta
from meritum_core.corpus.ready import STUB_WEIGHT, DocumentKind, GoldChunk, NumberTag

from meritum_worker.corpus.ready.acts import act_header, act_info, act_pieces
from meritum_worker.corpus.ready.constants import (
    CONSOLIDATED_TYPE,
    EXCERPT_CHARS,
    FULL_TEXT_KINDS,
    HEADING_MAX_CHARS,
    LEGAL_ACT_KIND,
    MAX_CHUNK_CHARS,
    NUMBER_PATTERN,
    SENTENCE_END,
    YEAR_PATTERN,
)
from meritum_worker.corpus.ready.models import BronzeDocument, Span
from meritum_worker.corpus.ready.silver import clean


def gold_chunks(
    doc: BronzeDocument, catalog_kind: str | None, meta: LegalActMeta | None
) -> list[GoldChunk]:
    """Chunk one bronze document for the gold layer.

    Args:
        doc: The live bronze document.
        catalog_kind: Its catalogue entry's ``kind``; None outside the catalogue.
        meta: Core's stored act metadata (core#167), None if absent.

    Returns:
        The chunks, each with ``text == doc.full_text[start_offset:end_offset]``.

    Features:
        US-KOR-02, US-ZRD-05, F-12
    """
    spans = clean(doc.full_text)
    if not spans:
        return []
    if catalog_kind == LEGAL_ACT_KIND:
        found = _act_chunks(doc, spans, meta)
        if found is not None:
            return found
    if catalog_kind in FULL_TEXT_KINDS:
        return _page_chunks(doc, spans)
    return [_excerpt(doc, spans[0])]


def _act_chunks(
    doc: BronzeDocument, spans: list[Span], meta: LegalActMeta | None
) -> list[GoldChunk] | None:
    info = act_info(doc.full_text, spans, meta)
    if info is None:
        return None
    header = act_header(info)
    consolidated = info.document_type == CONSOLIDATED_TYPE
    tags: dict[str, object] = {
        "kind": DocumentKind.CONSOLIDATED_TEXT if consolidated else DocumentKind.ACT,
        "eli": info.eli,
        "valid_from": info.in_force_from,
        "valid_to": info.in_force_until,
    }
    pieces = act_pieces(doc.full_text, spans, header)
    if not pieces:  # title-only act: findable, but ranks low
        return [_chunk(doc, 0, spans[0], header, tags | {"weight": STUB_WEIGHT})]
    return [
        _chunk(doc, n, p.span, p.header, tags | {"topic": p.chapter})
        for n, p in enumerate(pieces)
    ]


def _page_chunks(doc: BronzeDocument, spans: list[Span]) -> list[GoldChunk]:
    first = doc.full_text[spans[0].start : spans[0].end]
    title = first if _is_heading(first) else doc.domain
    base = f"{title} ({doc.domain}, {doc.published_on or 'bez daty'})."
    tags: dict[str, object] = {
        "kind": DocumentKind.NEWS,
        "subject": doc.domain.rsplit("/", 1)[-1],
    }
    sections = _sections(doc.full_text, spans)
    chunks = [
        _chunk(
            doc,
            n,
            span,
            base if heading is None else f"{base} {heading}.",
            tags | {"topic": heading},
        )
        for n, (heading, span) in enumerate(sections)
    ]
    # headings only: the title is all there is
    return chunks or [_chunk(doc, 0, spans[0], base, tags | {"weight": STUB_WEIGHT})]


def _sections(full_text: str, spans: list[Span]) -> list[tuple[str | None, Span]]:
    # Paragraphs grouped under their heading, at most MAX_CHUNK_CHARS per group.
    groups: list[tuple[str | None, Span]] = []
    heading: str | None = None
    open_group = False
    for span in spans:
        text = full_text[span.start : span.end]
        if _is_heading(text):
            heading, open_group = text, False
            continue
        last = groups[-1][1] if groups else None
        fits = last is not None and span.end - last.start <= MAX_CHUNK_CHARS
        if open_group and fits and last:
            groups[-1] = (heading, Span(start=last.start, end=span.end))
        else:
            groups.append((heading, span))
            open_group = True
    return groups


def _excerpt(doc: BronzeDocument, span: Span) -> GoldChunk:
    text = doc.full_text[span.start : span.end]
    if len(text) > EXCERPT_CHARS:
        cut = text.rfind(" ", 0, EXCERPT_CHARS)
        end = span.start + (cut if cut > 0 else EXCERPT_CHARS)
        span = Span(start=span.start, end=end)
    header = f"{doc.domain} ({doc.published_on or 'bez daty'}; wyimek)."
    tags = {"kind": DocumentKind.NEWS, "subject": doc.domain}
    return _chunk(doc, 0, span, header, tags)


def _chunk(
    doc: BronzeDocument, n: int, span: Span, header: str, tags: Mapping[str, object]
) -> GoldChunk:
    text = doc.full_text[span.start : span.end]
    return GoldChunk.model_validate(
        {
            "chunk_id": f"{doc.source_id}:{doc.checksum[:12]}:{n}",
            "source_id": doc.source_id,
            "checksum": doc.checksum,
            "start_offset": span.start,
            "end_offset": span.end,
            "text": text,
            "header": header,
            "published_on": doc.published_on,
            "numbers": number_tags(text),
            **tags,
        }
    )


def number_tags(text: str) -> tuple[NumberTag, ...]:
    """Numbers with unit and period stated in a chunk.

    Args:
        text: The chunk text.

    Returns:
        One tag per number; the period is a year in the same sentence, if any.

    Features:
        US-ZRD-05, F-12
    """
    tags: list[NumberTag] = []
    for sentence in re.split(SENTENCE_END, text):
        year = re.search(YEAR_PATTERN, sentence)
        for found in re.finditer(NUMBER_PATTERN, sentence):
            value = " ".join(found["value"].split())
            period = year[0] if year and year[0] != value else None
            tags.append(NumberTag(value=value, unit=found["unit"], period=period))
    return tuple(tags)


def _is_heading(text: str) -> bool:
    one_line = "\n" not in text
    return (
        one_line
        and len(text) <= HEADING_MAX_CHARS
        and not text.rstrip().endswith((".", ":", ";"))
    )
