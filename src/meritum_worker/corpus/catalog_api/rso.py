"""Communiqués of the Regional Warning System (RSO) from gov.pl's JSON proxy.

gov.pl's warnings page (``/web/gov/ostrzezenia``) is a JavaScript application
that reads them from ``/api/data/proxy/rso``, one list per province and
category; the same JSON is RSO's public API documented on
komunikaty.tvp.pl/Info/Integration. Alerts RCB are communiqués of the
``ogolne`` category.

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

from datetime import datetime

from pydantic import BaseModel

from meritum_worker.corpus.catalog_api.constants import RSO_DETAIL_URL, RSO_TIME
from meritum_worker.corpus.catalog_api.records import ApiRecord


class RsoProvince(BaseModel):
    """A province a communiqué covers; only the fields the parser reads.

    Attributes:
        name: The ``name`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    name: str


class RsoCommunique(BaseModel):
    """One communiqué; only the fields the parser reads.

    Attributes:
        id: The ``id`` field.
        title: The ``title`` field.
        shortcut: The ``shortcut`` field, a summary.
        content: The ``content`` field, the full text.
        valid_from: The ``valid_from`` field.
        valid_to: The ``valid_to`` field; None for no end.
        created_at: The ``created_at`` field, when RSO published it.
        provinces: The ``provinces`` field, keyed by province id.

    Features:
        US-KOR-02, F-10, F-12
    """

    id: int
    title: str
    shortcut: str | None = None
    content: str | None = None
    valid_from: datetime
    valid_to: datetime | None = None
    created_at: datetime
    provinces: dict[str, RsoProvince]


class RsoCommuniques(BaseModel):
    """One list of communiqués; only the fields the parser reads.

    Attributes:
        newses: The ``newses`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    newses: list[RsoCommunique]


def rso_communiques(category: str, text: str) -> list[ApiRecord]:
    """Communiqués of one RSO category, each a document of type „komunikat”.

    Args:
        category: The category's name, such as ``Ogólne``.
        text: The answer of ``/komunikatyxml/wszystkie/{slug}/0?_format=json``.

    Returns:
        One record per communiqué, dated by its publication in RSO and pointing
        at its page in gov.pl's warnings application.

    Features:
        US-KOR-02, F-10, F-12
    """
    return [
        ApiRecord(
            url=RSO_DETAIL_URL.format(id=item.id),
            text=_text(category, item),
            published_at=item.created_at.date(),
        )
        for item in RsoCommuniques.model_validate_json(text).newses
    ]


def _text(category: str, item: RsoCommunique) -> str:
    regions = ", ".join(p.name for p in item.provinces.values()) or "nie podano"
    until = item.valid_to.strftime(RSO_TIME) if item.valid_to else "odwołania"
    body = (item.content or item.shortcut or "").strip()
    return (
        f"{item.title}\n\nKomunikat RSO, kategoria: {category}. "
        f"Województwa: {regions}. "
        f"Ważny od {item.valid_from.strftime(RSO_TIME)} do {until}.\n\n{body}"
    )
