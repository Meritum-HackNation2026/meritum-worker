"""Steps of the page archive retention and erasure scenarios (security.feature).

They run on the in-memory archive registry and blob store; no database.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from behave import given, then
from behave.runner import Context
from meritum_core.shared.blobs import BlobKind, BlobNotFoundError
from meritum_core.shared.database import DatabaseSettings

from meritum_worker.corpus import ArchiveCopy
from meritum_worker.security import (
    InMemoryWorkflowStore,
    RetentionDeps,
    build_retention_deps,
)

NOW = datetime.now(UTC)
SESSION, OTHER = "s_12345678", "s_87654321"


async def _archive(deps: RetentionDeps, owner: str, expires_in: timedelta) -> str:
    """Store a page copy the way the archiving workflow does; return its blob id."""
    ref = await deps.archives.blobs.put(
        b"tekst strony",
        kind=BlobKind.DATASET,
        content_type="text/plain",
        expires_at=NOW + expires_in,
    )
    await deps.archives.registry.save(
        ArchiveCopy(
            archive_id=f"arch_{ref.blob_id}",
            blob_id=ref.blob_id,
            url="https://example.pl/a",
            owner_id=owner,
            sha256="0" * 64,
            archived_at=NOW - timedelta(days=30),
            expires_at=NOW + expires_in,
            legal_basis="podstawa",
            access_rule="reguła",
            deletion_procedure="procedura",
        )
    )
    return ref.blob_id


async def _archive_gone(deps: RetentionDeps, blob_id: str) -> bool:
    row = await deps.archives.registry.get(f"arch_{blob_id}")
    try:
        await deps.archives.blobs.get(blob_id)
    except BlobNotFoundError:
        return row is None
    return False


@given(
    "archiwum strony z expires_at we wczorajszej dacie i drugie ważne jeszcze 29 dni"
)
def archives_expired_and_fresh(context: Context) -> None:
    context.deps = build_retention_deps(
        DatabaseSettings(provider="memory"), None, workflows=InMemoryWorkflowStore()
    )
    context.gone = asyncio.run(_archive(context.deps, SESSION, timedelta(days=-1)))
    context.kept = asyncio.run(_archive(context.deps, SESSION, timedelta(days=29)))


@given("archiwum strony tej sesji oraz cudze")
def archives_of_session_and_other(context: Context) -> None:
    context.gone = asyncio.run(
        _archive(context.deps, context.session, timedelta(days=20))
    )
    context.kept = asyncio.run(_archive(context.deps, OTHER, timedelta(days=20)))


@then("wygasłe archiwum nie ma wiersza ani pliku, a ważne zostaje")
@then("archiwum tej sesji nie ma wiersza ani pliku, a cudze zostaje")
def archive_is_gone_and_other_stays(context: Context) -> None:
    assert asyncio.run(_archive_gone(context.deps, context.gone))
    assert not asyncio.run(_archive_gone(context.deps, context.kept))
