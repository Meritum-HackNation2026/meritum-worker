"""The organiser's files (§7 of the task): incidents, sources and the import report.

The format is confirmed once the files arrive; until then these models follow
§7: JSON or CSV, each record with a date, a licence and a thematic scope.

Features:
    US-KOR-02, US-ZRD-08, US-OBS-04, F-10, F-11, ADR-32
"""

from datetime import UTC, date, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from meritum_worker.corpus.organiser.constants import TOPIC_SEPARATOR


def _split_topics(value: object) -> object:
    if isinstance(value, str):
        return [t.strip() for t in value.split(TOPIC_SEPARATOR) if t.strip()]
    return value


class OrganiserIncident(BaseModel):
    """One incident of the organiser's incident database.

    Attributes:
        id: The record's id in the file; the import is idempotent on it.
        title: Short name of the incident.
        description: What was claimed (source text: data); embedded for search.
        date: When it happened; a bare date means midnight UTC.
        license: The licence the organiser gives for the record.
        topics: Thematic scope; ``a;b`` in a CSV cell.
        retention_days: How long the record may be kept, if the file says.
        url: Where the incident is described, if anywhere.
        fact: The disproof, if the file gives one.

    Features:
        US-KOR-02, US-ZRD-08, F-10, F-11
    """

    model_config = ConfigDict(
        frozen=True, coerce_numbers_to_str=True, str_strip_whitespace=True
    )

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    date: AwareDatetime | date
    license: str = Field(min_length=1)
    topics: tuple[str, ...] = Field(min_length=1)
    retention_days: int | None = Field(default=None, ge=1)
    url: str | None = None
    fact: str | None = None

    @field_validator("topics", mode="before")
    @classmethod
    def _split(cls, value: object) -> object:
        return _split_topics(value)

    def published_at(self) -> datetime:
        """The incident's date as an aware datetime.

        Returns:
            ``date`` itself, or midnight UTC of a bare date.

        Features:
            US-KOR-02, F-11
        """
        if isinstance(self.date, datetime):
            return self.date
        return datetime(self.date.year, self.date.month, self.date.day, tzinfo=UTC)


class OrganiserSource(BaseModel):
    """One source of the organiser's source list.

    Attributes:
        id: The record's id in the file.
        name: Name of the source.
        url: The source's address.
        date: When the organiser listed it.
        license: The licence the organiser gives.
        topics: Thematic scope.

    Features:
        US-KOR-02, F-10
    """

    model_config = ConfigDict(
        frozen=True, coerce_numbers_to_str=True, str_strip_whitespace=True
    )

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    date: AwareDatetime | date
    license: str = Field(min_length=1)
    topics: tuple[str, ...] = Field(min_length=1)

    @field_validator("topics", mode="before")
    @classmethod
    def _split(cls, value: object) -> object:
        return _split_topics(value)


class SkippedRecord(BaseModel):
    """A record the import left out, with why.

    Attributes:
        id: The record's id, or its position (``#3``) when it has none.
        reason: ``missing_license`` or ``invalid_record``.
        detail: The fields that failed validation.

    Features:
        US-KOR-02, F-10
    """

    model_config = ConfigDict(frozen=True)

    id: str
    reason: str
    detail: str = ""


class ImportReport(BaseModel):
    """What one import of an organiser's file did.

    Attributes:
        added: New incidents in the local copy.
        updated: Incidents whose content changed.
        unchanged: Incidents already stored as they are in the file.
        sources: Valid records of a source list.
        skipped: Records left out, each with its reason.
        disabled: The import did not run: this worker may not write ``corpus``.

    Features:
        US-KOR-02, US-ZRD-08, F-10, F-11
    """

    model_config = ConfigDict(frozen=True)

    added: int = 0
    updated: int = 0
    unchanged: int = 0
    sources: int = 0
    skipped: tuple[SkippedRecord, ...] = ()
    disabled: bool = False
