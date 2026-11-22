"""Parsers of the catalogue's public APIs: the raw JSON answer to records.

Each answer is validated by a pydantic model in ``answers`` with only the fields
the record uses; a ``ValidationError`` (a ``ValueError``) becomes
``InvalidApiResponseError`` in ``parse_listing``.

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

import re
from datetime import date

from pydantic import RootModel

from meritum_worker.corpus.catalog_api.answers import (
    BdlSubjects,
    DaneDatasets,
    JsonStat,
    NbpGold,
    NbpTable,
    SejmActs,
)
from meritum_worker.corpus.catalog_api.constants import (
    BDL_SUBJECT_URL,
    DANE_DATASET_URL,
    EUROSTAT_GEO,
    EUROSTAT_TIME,
    HTML_TAG,
    NBP_GOLD_DAY_URL,
    NBP_TABLE_URL,
    SEJM_ELI_ACT_URL,
)
from meritum_worker.corpus.catalog_api.records import ApiRecord


def sejm_acts(text: str) -> list[ApiRecord]:
    """Acts of Dziennik Ustaw from the Sejm's ELI API.

    Args:
        text: The answer of ``/eli/acts/DU/{year}``.

    Returns:
        One record per act, dated by its promulgation.

    Features:
        US-KOR-02, F-10, F-12
    """
    return [
        ApiRecord(
            url=SEJM_ELI_ACT_URL.format(eli=act.eli),
            text=(
                f"{act.title}\n\n{act.type}, status: {act.status}. "
                f"{act.display_address}, ogłoszono {act.promulgation}."
            ),
            published_at=act.promulgation,
        )
        for act in SejmActs.model_validate_json(text).items
    ]


def nbp_tables(text: str) -> list[ApiRecord]:
    """NBP's tables A of average exchange rates.

    Args:
        text: The answer of ``/api/exchangerates/tables/A/...``.

    Returns:
        One record per table, dated by its effective date.

    Features:
        US-KOR-02, F-10, F-12
    """
    records = []
    for table in RootModel[list[NbpTable]].model_validate_json(text).root:
        day = table.effective_date
        lines = [f"Tabela kursów średnich NBP nr {table.no} z dnia {day}."]
        lines += [
            f"Średni kurs NBP: {rate.currency} ({rate.code}) = {rate.mid} zł."
            for rate in table.rates
        ]
        url = NBP_TABLE_URL.format(day=day)
        records.append(ApiRecord(url=url, text="\n".join(lines), published_at=day))
    return records


def nbp_gold(text: str) -> list[ApiRecord]:
    """NBP's gold prices.

    Args:
        text: The answer of ``/api/cenyzlota/...``.

    Returns:
        One record per day.

    Features:
        US-KOR-02, F-10, F-12
    """
    return [
        ApiRecord(
            url=NBP_GOLD_DAY_URL.format(day=gold.day),
            text=(
                f"Cena 1 g złota (próba 1000) według NBP z dnia {gold.day}: "
                f"{gold.price} zł."
            ),
            published_at=gold.day,
        )
        for gold in RootModel[list[NbpGold]].model_validate_json(text).root
    ]


def dane_datasets(text: str) -> list[ApiRecord]:
    """Datasets of dane.gov.pl; each names its own licence in the text.

    Args:
        text: The JSON:API answer of ``/1.4/datasets``.

    Returns:
        One record per dataset, dated by its last change.

    Features:
        US-KOR-02, F-10, F-12
    """
    records = []
    for dataset in DaneDatasets.model_validate_json(text).data:
        fields = dataset.attributes
        notes = " ".join(re.sub(HTML_TAG, " ", fields.notes or "").split())
        licence = fields.license_name or "nie podano"
        records.append(
            ApiRecord(
                url=DANE_DATASET_URL.format(id=dataset.id, slug=fields.slug),
                text=f"{fields.title}\n\n{notes}\n\nLicencja zbioru: {licence}.",
                published_at=fields.modified.date(),
            )
        )
    return records


def bdl_subjects(text: str) -> list[ApiRecord]:
    """Subject areas of GUS's Bank Danych Lokalnych.

    Args:
        text: The answer of ``/api/v1/subjects``.

    Returns:
        One record per subject area, undated.

    Features:
        US-KOR-02, F-10, F-12
    """
    return [
        ApiRecord(
            url=BDL_SUBJECT_URL.format(id=subject.id),
            text=f"Dziedzina Banku Danych Lokalnych GUS {subject.id}: {subject.name}.",
        )
        for subject in BdlSubjects.model_validate_json(text).results
    ]


def eurostat_series(url: str, text: str) -> list[ApiRecord]:
    """One JSON-stat 2.0 series of Eurostat, every dimension but time filtered.

    Args:
        url: The query; the record keeps it as its address.
        text: The JSON-stat dataset.

    Returns:
        One record with every period's value, dated by the last update.

    Raises:
        ValueError: A dimension other than time has more than one value.

    Features:
        US-KOR-02, F-10, F-12
    """
    data = JsonStat.model_validate_json(text)
    sizes = dict(zip(data.id, data.size, strict=True))
    if any(size != 1 for name, size in sizes.items() if name != EUROSTAT_TIME):
        msg = "more than one series"
        raise ValueError(msg)
    time = data.dimension[EUROSTAT_TIME].category
    geo = data.dimension[EUROSTAT_GEO].category.label.values()
    lines = [f"{data.label}: {', '.join(geo)} (Eurostat)."]
    for period, index in sorted(time.index.items(), key=lambda item: item[1]):  # ruff: ignore[reimplemented-operator]  # clearer than itemgetter
        value = (
            data.value.get(str(index))
            if isinstance(data.value, dict)
            else data.value[index]
        )
        if value is not None:
            lines.append(f"{time.label.get(period, period)}: {value}")
    published = date.fromisoformat(data.updated[:10])
    return [ApiRecord(url=url, text="\n".join(lines), published_at=published)]
