"""Legal acts from the Sejm's ELI API with their full text.

An act's ELI entry gives its metadata and names its text files. The record
points at the consolidated PDF (``U``) when there is one, else at the journal
text (``text.pdf``); the HTML of older acts is not used, because core's
extractor keeps only part of it. ``act_body`` turns the PDF's pages into
paragraphs, one per article, and ``act_parts`` cuts a long act into documents
the injection classifier reads whole.

Features:
    US-KOR-02, US-ZRD-05, F-10, F-12
"""

import dataclasses
import re
from datetime import date

from pydantic import BaseModel, Field

from meritum_worker.corpus.catalog_api.constants import (
    ACT_PAGE_HEADER,
    ACT_PART_MAX_CHARS,
    ACT_PART_URL,
    ACT_UNIT_START,
    PDF_PAGE_BREAK,
    PDF_SOFT_HYPHEN,
    SEJM_CONSOLIDATED_TEXT,
    SEJM_ELI_ACT_URL,
    SEJM_ELI_FILE_URL,
    SEJM_ELI_PDF_URL,
)
from meritum_worker.corpus.catalog_api.records import ApiRecord
from meritum_worker.corpus.chunking import chunk_text
from meritum_worker.corpus.constants import PARAGRAPH_SEPARATOR


class _TextFile(BaseModel):
    name: str = Field(alias="fileName", pattern=r"^[A-Za-z0-9_.-]+$")
    kind: str = Field(alias="type", pattern=r"^[A-Z]$")


class _Act(BaseModel):
    eli: str = Field(alias="ELI")
    title: str = Field(min_length=1)
    type: str
    status: str
    display_address: str = Field(alias="displayAddress")
    announced: date = Field(alias="announcementDate")
    promulgation: date | None = None
    in_force_from: date | None = Field(default=None, alias="entryIntoForce")
    has_pdf: bool = Field(default=False, alias="textPDF")
    texts: list[_TextFile] = []


class _Acts(BaseModel):
    items: list[_Act]


def sejm_act(text: str) -> list[ApiRecord]:
    """One act from its ELI entry, ``/eli/acts/{publisher}/{year}/{position}``.

    Args:
        text: The raw, untrusted JSON answer.

    Returns:
        One record of the act's metadata that wants the act's full text.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """
    return [_record(_Act.model_validate_json(text))]


def sejm_act_search(text: str) -> list[ApiRecord]:
    """Acts from an ELI search, ``/eli/acts/search``, each with its full text.

    Args:
        text: The raw, untrusted JSON answer.

    Returns:
        One record per act, as ``sejm_act`` makes it.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """
    return [_record(act) for act in _Acts.model_validate_json(text).items]


def _record(act: _Act) -> ApiRecord:
    in_force = f", w mocy od {act.in_force_from}" if act.in_force_from else ""
    published = act.promulgation or act.announced
    header = (
        f"{act.title}\n\n{act.type}, ELI: {act.eli}, {act.display_address}, "
        f"status: {act.status}{in_force}, ogłoszono {published}."
    )
    return ApiRecord(
        url=SEJM_ELI_ACT_URL.format(eli=act.eli),
        text=header,
        published_at=published,
        wants_text=True,
        text_url=_text_url(act),
    )


def _text_url(act: _Act) -> str | None:
    for file in act.texts:
        if file.kind == SEJM_CONSOLIDATED_TEXT:
            return SEJM_ELI_FILE_URL.format(eli=act.eli, kind=file.kind, name=file.name)
    return SEJM_ELI_PDF_URL.format(eli=act.eli) if act.has_pdf else None


def act_body(text: str) -> str:
    """The text of an act's PDF as paragraphs: one per article or chapter.

    Running heads at the top of each page are dropped, and so is PDFium's mark of
    a word split at a line end. Lines within a unit stay as they are.

    Args:
        text: The PDF's pages separated by ``PDF_PAGE_BREAK`` (untrusted data).

    Returns:
        The body; empty for a PDF with no text layer.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """
    lines = [
        line
        for page in text.replace(PDF_SOFT_HYPHEN, "").split(PDF_PAGE_BREAK)
        for line in _without_heads(page.splitlines())
    ]
    units: list[list[str]] = []
    for line in lines:
        if not units or re.match(ACT_UNIT_START, line):
            units.append([])
        units[-1].append(line)
    return PARAGRAPH_SEPARATOR.join("\n".join(unit) for unit in units)


def _without_heads(lines: list[str]) -> list[str]:
    kept = [line.strip() for line in lines]
    while kept and (not kept[0] or re.match(ACT_PAGE_HEADER, kept[0])):
        kept.pop(0)
    return [line for line in kept if line]


def act_parts(record: ApiRecord, body: str) -> list[ApiRecord]:
    """The act as documents of at most ``ACT_PART_MAX_CHARS`` of body each.

    Passages are grouped in order; every part opens with the act's metadata.
    The first part keeps the act's URL, the next ones add ``#czesc-N``.

    Args:
        record: The act's metadata record.
        body: ``act_body`` of its text.

    Returns:
        One record per part, none wanting more text.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """
    groups: list[str] = []
    for passage in chunk_text(body):
        joined = f"{groups[-1]}{PARAGRAPH_SEPARATOR}{passage}" if groups else passage
        if groups and len(joined) <= ACT_PART_MAX_CHARS:
            groups[-1] = joined
        else:
            groups.append(passage)
    return [
        dataclasses.replace(
            record,
            url=record.url if n == 1 else ACT_PART_URL.format(url=record.url, number=n),
            text=f"{record.text}{PARAGRAPH_SEPARATOR}{group}",
            wants_text=False,
            text_url=None,
        )
        for n, group in enumerate(groups, start=1)
    ]
