"""Import of the organiser's materials into the local incident copy.

Incidents go to the same copy as EUvsDisinfo cases (``kind = case``, ``database
= organiser``), so incident matching reads both with one function. The import
only adds and updates: an incident missing from a later file stays.

Features:
    US-KOR-02, US-ZRD-08, F-10, F-11, ADR-32
"""

from collections.abc import Mapping, Sequence
from itertools import batched
from pathlib import Path

from meritum_core.shared.embeddings import EmbeddingsPort, Vector
from pydantic import BaseModel, ValidationError

from meritum_worker.corpus.ingest import ingestion_enabled
from meritum_worker.corpus.models import Entry, StoredEntry
from meritum_worker.corpus.organiser.constants import (
    DATABASE,
    EMBED_BATCH,
    INCIDENT_KEY_PREFIX,
    INVALID_RECORD,
    MISSING_LICENSE,
)
from meritum_worker.corpus.organiser.models import (
    ImportReport,
    OrganiserIncident,
    OrganiserSource,
    SkippedRecord,
)
from meritum_worker.corpus.organiser.ports import OrganiserFilePort
from meritum_worker.corpus.ports import EuvsCopyPort


def validated[M: BaseModel](
    records: Sequence[Mapping[str, object]], model: type[M]
) -> tuple[list[M], list[SkippedRecord]]:
    """Validate each record; a bad one is skipped with its reason, not raised.

    Args:
        records: Raw records from the file.
        model: ``OrganiserIncident`` or ``OrganiserSource``.

    Returns:
        The valid records and the skipped ones.

    Features:
        US-KOR-02, F-10
    """
    valid: list[M] = []
    skipped: list[SkippedRecord] = []
    for position, record in enumerate(records, start=1):
        try:
            valid.append(model.model_validate(record))
        except ValidationError as error:
            skipped.append(_skipped(record, position, error))
    return valid, skipped


async def import_organiser_file(
    path: Path,
    files: OrganiserFilePort,
    store: EuvsCopyPort,
    embeddings: EmbeddingsPort,
    *,
    env: Mapping[str, str],
) -> ImportReport:
    """The body of the import workflow: one incident file or one source list.

    Args:
        path: The file; ``sources`` in its name marks a source list.
        files: Reads the file.
        store: The local incident copy.
        embeddings: Multilingual embeddings of the descriptions and facts.
        env: The worker's environment; the import runs only where ingestion
            may write the shared ``corpus`` schema.

    Returns:
        The report; ``disabled`` without reading the file where ingestion is off.

    Features:
        US-KOR-02, US-ZRD-08, F-10, F-11, ADR-32
    """
    if not ingestion_enabled(env):
        return ImportReport(disabled=True)
    records = await files.records(path)
    if "sources" in path.stem:
        sources, skipped = validated(records, OrganiserSource)
        return ImportReport(sources=len(sources), skipped=tuple(skipped))
    incidents, skipped = validated(records, OrganiserIncident)
    return await import_incidents(incidents, store, embeddings, skipped=skipped)


async def import_incidents(
    incidents: Sequence[OrganiserIncident],
    store: EuvsCopyPort,
    embeddings: EmbeddingsPort,
    *,
    skipped: Sequence[SkippedRecord] = (),
) -> ImportReport:
    """Write the incidents that are new or changed; same id twice counts once.

    Args:
        incidents: Validated incidents.
        store: The local incident copy.
        embeddings: Multilingual embeddings.
        skipped: Records already left out, carried into the report.

    Returns:
        Added, updated and unchanged incidents, and the skipped records.

    Features:
        US-KOR-02, US-ZRD-08, F-11
    """
    entries = list({e.key: e for e in map(_entry, incidents)}.values())
    stored = {s.entry.key: s for s in await store.entries()}
    fresh = [e for e in entries if _changed(e, stored.get(e.key))]
    await store.upsert(await _embedded(fresh, embeddings))
    added = sum(e.key not in stored for e in fresh)
    return ImportReport(
        added=added,
        updated=len(fresh) - added,
        unchanged=len(entries) - len(fresh),
        skipped=tuple(skipped),
    )


def _skipped(
    record: Mapping[str, object], position: int, error: ValidationError
) -> SkippedRecord:
    fields = sorted({str(e["loc"][0]) for e in error.errors() if e["loc"]})
    reason = MISSING_LICENSE if "license" in fields else INVALID_RECORD
    record_id = str(record.get("id") or f"#{position}")
    return SkippedRecord(id=record_id, reason=reason, detail=", ".join(fields))


def _entry(incident: OrganiserIncident) -> Entry:
    return Entry(
        key=f"{INCIDENT_KEY_PREFIX}{incident.id}",
        kind="case",
        title=incident.title,
        url=incident.url or "",
        published_at=incident.published_at(),
        description=incident.description,
        fact=incident.fact,
        database=DATABASE,
        license=incident.license,
        retention_days=incident.retention_days,
        topics=incident.topics,
    )


def _changed(entry: Entry, stored: StoredEntry | None) -> bool:
    return stored is None or stored.deleted_at is not None or stored.entry != entry


async def _embedded(
    entries: Sequence[Entry], embeddings: EmbeddingsPort
) -> list[StoredEntry]:
    descriptions = await _embed([e.description for e in entries], embeddings)
    with_fact = [e for e in entries if e.fact is not None]
    facts = await _embed([e.fact or "" for e in with_fact], embeddings)
    fact_vectors = dict(zip((e.key for e in with_fact), facts, strict=True))
    return [
        StoredEntry(
            entry=entry,
            description_vector=vector,
            fact_vector=fact_vectors.get(entry.key),
        )
        for entry, vector in zip(entries, descriptions, strict=True)
    ]


async def _embed(texts: Sequence[str], embeddings: EmbeddingsPort) -> list[Vector]:
    vectors: list[Vector] = []
    for chunk in batched(texts, EMBED_BATCH, strict=False):
        vectors += await embeddings.embed_documents(chunk)
    return vectors
