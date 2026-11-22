"""Metadata of a legal act from ELI and its text split into units (articles).

``LegalActMeta`` carries the fields other corpus layers read about an act (kind
of document, when it is in force, ELI, journal position); the names are agreed
on worker#162. The worker's document row has no column for them yet, so they
live on the ingestion record and in the document's header text.

Features:
    US-KOR-02, US-ZRD-05, F-10, F-12
"""

import re
from datetime import date

from pydantic import BaseModel, ConfigDict

from meritum_worker.corpus.catalog_api.constants import ACT_UNIT_START
from meritum_worker.corpus.constants import PARAGRAPH_SEPARATOR


class LegalActMeta(BaseModel):
    """What ELI says about one act.

    Attributes:
        eli: The act's ELI, such as ``DU/1997/483``.
        title: The act's title.
        document_type: ELI ``type``: ``Ustawa``, ``Rozporządzenie``, ``Obwieszczenie``.
        legal_status: ELI ``status``: ``obowiązujący``, ``akt jednorazowy``,
            ``wygaśnięcie aktu`` and so on.
        in_force: ELI ``inForce`` is ``IN_FORCE``.
        in_force_from: ELI ``validFrom``, else ``entryIntoForce``; None if absent.
        in_force_until: ELI ``expirationDate``; None for an act still in force.
        journal_publisher: ``DU`` (Dziennik Ustaw) or ``MP`` (Monitor Polski).
        journal_year: The journal's year.
        journal_position: The position in that year's journal.
        display_address: The citation, such as ``Dz.U. 1997 nr 78 poz. 483``.
        published_on: Promulgation date, else announcement date.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """

    model_config = ConfigDict(frozen=True)

    eli: str
    title: str
    document_type: str
    legal_status: str
    in_force: bool
    in_force_from: date | None
    in_force_until: date | None
    journal_publisher: str
    journal_year: int
    journal_position: int
    display_address: str
    published_on: date


class ActUnit(BaseModel):
    """One unit of an act's text: an article, a paragraph (§) or a chapter.

    Attributes:
        label: The unit's opening, such as ``Art. 29.``, ``§ 1.`` or
            ``Rozdział``; empty for the text before the first unit (a preamble).
        text: The unit's whole text, label included.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """

    model_config = ConfigDict(frozen=True)

    label: str
    text: str


def act_units(body: str) -> list[ActUnit]:
    """Split ``act_body`` text into its articles, paragraphs and chapters.

    ``act_body`` already starts each unit on a new paragraph; numbered
    subsections (``ust.``) stay inside their article.

    Args:
        body: ``act_body`` of an act's text (untrusted data).

    Returns:
        The units in order; empty for blank text.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """
    units = []
    for paragraph in body.split(PARAGRAPH_SEPARATOR):
        text = paragraph.strip()
        if text:
            found = re.match(ACT_UNIT_START, text)
            units.append(ActUnit(label=found[0].strip() if found else "", text=text))
    return units
