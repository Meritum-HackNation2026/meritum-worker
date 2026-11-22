"""Pydantic models of the public API answers; only the fields the records use.

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class SejmAct(BaseModel):
    """One act in the ELI listing; only the fields the parser reads.

    Attributes:
        eli: The ``ELI`` field.
        title: The ``title`` field.
        type: The ``type`` field.
        status: The ``status`` field.
        display_address: The ``displayAddress`` field.
        promulgation: The ``promulgation`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    eli: str = Field(alias="ELI")
    title: str
    type: str
    status: str
    display_address: str = Field(alias="displayAddress")
    promulgation: date


class SejmActs(BaseModel):
    """The ELI listing of one year; only the fields the parser reads.

    Attributes:
        items: The ``items`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    items: list[SejmAct]


class NbpRate(BaseModel):
    """One average rate; only the fields the parser reads.

    Attributes:
        currency: The ``currency`` field.
        code: The ``code`` field.
        mid: The ``mid`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    currency: str
    code: str
    mid: float


class NbpTable(BaseModel):
    """One table A; only the fields the parser reads.

    Attributes:
        no: The ``no`` field.
        effective_date: The ``effectiveDate`` field.
        rates: The ``rates`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    no: str
    effective_date: date = Field(alias="effectiveDate")
    rates: list[NbpRate]


class NbpGold(BaseModel):
    """One day's gold price; only the fields the parser reads.

    Attributes:
        day: The ``data`` field.
        price: The ``cena`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    day: date = Field(alias="data")
    price: float = Field(alias="cena")


class DaneDatasetFields(BaseModel):
    """The JSON:API attributes of a dataset; only the fields the parser reads.

    Attributes:
        title: The ``title`` field.
        slug: The ``slug`` field.
        modified: The ``modified`` field.
        notes: The ``notes`` field.
        license_name: The ``license_name`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    title: str
    slug: str
    modified: datetime
    notes: str | None = None
    license_name: str | None = None


class DaneDataset(BaseModel):
    """One JSON:API dataset; only the fields the parser reads.

    Attributes:
        id: The ``id`` field.
        attributes: The ``attributes`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    id: str
    attributes: DaneDatasetFields


class DaneDatasets(BaseModel):
    """One page of datasets; only the fields the parser reads.

    Attributes:
        data: The ``data`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    data: list[DaneDataset]


class BdlSubject(BaseModel):
    """One subject area; only the fields the parser reads.

    Attributes:
        id: The ``id`` field.
        name: The ``name`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    id: str
    name: str


class BdlSubjects(BaseModel):
    """One page of subject areas; only the fields the parser reads.

    Attributes:
        results: The ``results`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    results: list[BdlSubject]


class JsonStatCategory(BaseModel):
    """The values of one JSON-stat dimension; only the fields the parser reads.

    Attributes:
        index: The ``index`` field.
        label: The ``label`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    index: dict[str, int]
    label: dict[str, str]


class JsonStatDimension(BaseModel):
    """One JSON-stat dimension; only the fields the parser reads.

    Attributes:
        category: The ``category`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    category: JsonStatCategory


class JsonStat(BaseModel):
    """A JSON-stat 2.0 dataset; only the fields the parser reads.

    Attributes:
        label: The ``label`` field.
        updated: The ``updated`` field.
        id: The ``id`` field.
        size: The ``size`` field.
        value: The ``value`` field.
        dimension: The ``dimension`` field.

    Features:
        US-KOR-02, F-10, F-12
    """

    label: str
    updated: str
    id: list[str]
    size: list[int]
    value: dict[str, float | None] | list[float | None]
    dimension: dict[str, JsonStatDimension]
