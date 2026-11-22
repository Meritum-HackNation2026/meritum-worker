"""Gold chunks of a legal act: one per article or §, long ones split by ``ust.``.

Units come from ``catalog_api.act_units`` (Łukasz's parser, worker#249); this
module only groups them and writes headers. Headers are search context and are
never citable: the chunk text stays a bronze span.

Features:
    US-KOR-02, US-ZRD-05, F-12
"""

import re
from datetime import date

from meritum_core.corpus import LegalActMeta
from pydantic import BaseModel, ConfigDict

from meritum_worker.corpus.catalog_api import act_units
from meritum_worker.corpus.ready.constants import (
    ACT_META_LINE,
    CHAPTER_LABELS,
    MAX_CHUNK_CHARS,
    SUBSECTION_START,
)
from meritum_worker.corpus.ready.models import Span


class ActInfo(BaseModel):
    """What a gold header says about an act (worker#162 field names).

    Attributes:
        title: The act's title.
        eli: Its ELI.
        document_type: ELI ``type``.
        legal_status: ELI ``status``.
        display_address: The journal citation.
        in_force_from: First day in force.
        in_force_until: Last day in force.

    Features:
        US-KOR-02, US-ZRD-05, F-12
    """

    model_config = ConfigDict(frozen=True)

    title: str
    eli: str
    document_type: str
    legal_status: str
    display_address: str
    in_force_from: date | None
    in_force_until: date | None


class ActPiece(BaseModel):
    """One act chunk before tags and embedding.

    Attributes:
        span: Its bronze characters.
        header: Act header, chapter and, for a continuation, ``Art. N. (cd.)``.
        chapter: The chapter heading, None before the first chapter.

    Features:
        US-KOR-02, F-12
    """

    model_config = ConfigDict(frozen=True)

    span: Span
    header: str
    chapter: str | None


def act_info(
    full_text: str, spans: list[Span], meta: LegalActMeta | None
) -> ActInfo | None:
    """The act's header facts: core's stored metadata, else the document header.

    Args:
        full_text: The bronze text.
        spans: Its silver spans; the first is the title, the second the metadata.
        meta: Core's ``document_legal_meta`` row (core#167), None if not stored.

    Returns:
        The facts, or None when the text has no act header.

    Features:
        US-KOR-02, US-ZRD-05, F-12
    """
    if len(spans) < 2:  # ruff: ignore[magic-value-comparison]  # title and metadata line
        return None
    title = full_text[spans[0].start : spans[0].end]
    if meta is not None:
        return ActInfo(
            title=title, **meta.model_dump(include=set(ActInfo.model_fields))
        )
    found = re.match(ACT_META_LINE, full_text[spans[1].start : spans[1].end])
    if found is None:
        return None
    return ActInfo(
        title=title,
        eli=found["eli"],
        document_type=found["type"],
        legal_status=found["status"],
        display_address=found["address"],
        in_force_from=found["since"],
        in_force_until=found["until"],
    )


def act_header(info: ActInfo) -> str:
    """The context line every chunk of the act gets.

    Args:
        info: The act's facts.

    Returns:
        ``{title} ({address}; {type}; status: …, w mocy od … do …).``

    Features:
        US-KOR-02, US-ZRD-05, F-12
    """
    since = f", w mocy od {info.in_force_from}" if info.in_force_from else ""
    until = f" do {info.in_force_until}" if info.in_force_until else ""
    return (
        f"{info.title} ({info.display_address}; {info.document_type}; "
        f"status: {info.legal_status}{since}{until})."
    )


def act_pieces(full_text: str, spans: list[Span], header: str) -> list[ActPiece]:
    """Chunk the act body (spans after the title and metadata line).

    Args:
        full_text: The bronze text.
        spans: Its silver spans.
        header: ``act_header`` of the act.

    Returns:
        One piece per article or §, or per group of ``ust.`` of a long one.

    Features:
        US-KOR-02, US-ZRD-05, F-12
    """
    pieces: list[ActPiece] = []
    chapter: str | None = None
    article = ""  # ingest may cut a long article into paragraphs (chunk_text)
    for span in spans[2:]:
        text = full_text[span.start : span.end]
        units = act_units(text)
        label = units[0].label if units else ""
        if label.startswith(CHAPTER_LABELS):
            chapter = " ".join(text.split())
            continue
        context = header if chapter is None else f"{header} {chapter}."
        for n, part in enumerate(_split(text, span.start)):
            own = label if n == 0 else ""
            article = own or article
            cont = f" {article} (cd.)" if article and not own else ""
            pieces.append(ActPiece(span=part, header=context + cont, chapter=chapter))
    return pieces


def _split(text: str, offset: int) -> list[Span]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [Span(start=offset, end=offset + len(text))]
    bounds = [0, *(m.start() for m in re.finditer(SUBSECTION_START, text) if m.start())]
    groups: list[tuple[int, int]] = []
    for begin, end in zip(bounds, [*bounds[1:], len(text)], strict=True):
        if groups and end - groups[-1][0] <= MAX_CHUNK_CHARS:
            groups[-1] = (groups[-1][0], end)
        else:
            groups.append((begin, end))
    return [_trim(text, offset, begin, end) for begin, end in groups]


def _trim(text: str, offset: int, begin: int, end: int) -> Span:
    piece = text[begin:end]
    lead = len(piece) - len(piece.lstrip())
    return Span(start=offset + begin + lead, end=offset + begin + len(piece.rstrip()))
