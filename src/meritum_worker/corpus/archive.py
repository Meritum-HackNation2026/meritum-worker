"""Controlled archiving of one public page, on a citizen's request only.

The text goes to the ``BlobStore`` with its hash and time, never to the corpus.
The page is read through core's SSRF-safe fetcher as a source, so robots.txt and
the TDM reservation hold; a login wall or paywall is never worked around.

Features:
    US-KOR-07, F-38
"""

import hashlib
from datetime import datetime

from meritum_core.corpus.fetching import (
    FetchFailureReason,
    FetchPurpose,
    LoginWallError,
    PageFetchError,
)
from meritum_core.shared.blobs import BlobKind

from meritum_worker.corpus.archive_constants import (
    ARCHIVE_ACCESS_RULE,
    ARCHIVE_CONTENT_TYPE,
    ARCHIVE_DELETION_PROCEDURE,
    ARCHIVE_LEGAL_BASIS,
    ARCHIVE_RATE_LIMIT,
    ARCHIVE_RATE_WINDOW,
    ARCHIVE_RETENTION,
    MESSAGE_FETCH_FAILED,
    MESSAGE_PAYWALL,
    MESSAGE_RATE_LIMIT,
    MESSAGE_ROBOTS,
)
from meritum_worker.corpus.archive_models import (
    ArchiveCopy,
    ArchiveOutcome,
    ArchiveRefusal,
    ArchiveRequest,
)
from meritum_worker.corpus.archive_ports import ArchiveDeps
from meritum_worker.corpus.errors import ArchiveAccessDeniedError


def _refused(refusal: ArchiveRefusal, message: str) -> ArchiveOutcome:
    return ArchiveOutcome(refusal=refusal, message=message)


def _fetch_refusal(error: PageFetchError) -> ArchiveOutcome:
    if isinstance(error, LoginWallError):
        return _refused(ArchiveRefusal.LOGIN_WALL, MESSAGE_PAYWALL)
    if error.reason == FetchFailureReason.ROBOTS_DISALLOWED:
        return _refused(ArchiveRefusal.ROBOTS_OR_TDM, MESSAGE_ROBOTS)
    return _refused(ArchiveRefusal.FETCH_FAILED, MESSAGE_FETCH_FAILED)


async def archive_page(
    request: ArchiveRequest, deps: ArchiveDeps, *, now: datetime
) -> ArchiveOutcome:
    """Archive one public page for the person who asked.

    Args:
        request: the page and who asked.
        deps: the fetcher, blob store and registry.
        now: the archiving time.

    Returns:
        The stored copy, or a refusal with the message the citizen sees: a login
        wall or paywall, robots.txt or TDM, a failed fetch or the rate limit.

    Features:
        US-KOR-07, F-38
    """
    made = await deps.registry.count_since(request.owner_id, now - ARCHIVE_RATE_WINDOW)
    if made >= ARCHIVE_RATE_LIMIT:
        return _refused(ArchiveRefusal.RATE_LIMITED, MESSAGE_RATE_LIMIT)
    try:
        page = await deps.pages.fetch(request.url, purpose=FetchPurpose.SOURCE)
    except PageFetchError as error:
        return _fetch_refusal(error)
    if page.tdm_reserved:
        return _refused(ArchiveRefusal.ROBOTS_OR_TDM, MESSAGE_ROBOTS)
    data = page.untrusted_text.encode()
    expires_at = now + ARCHIVE_RETENTION
    ref = await deps.blobs.put(
        data,
        kind=BlobKind.DATASET,
        content_type=ARCHIVE_CONTENT_TYPE,
        expires_at=expires_at,
    )
    copy = ArchiveCopy(
        archive_id=ref.blob_id,
        blob_id=ref.blob_id,
        url=page.url,
        owner_id=request.owner_id,
        sha256=hashlib.sha256(data).hexdigest(),
        archived_at=now,
        expires_at=expires_at,
        legal_basis=ARCHIVE_LEGAL_BASIS,
        access_rule=ARCHIVE_ACCESS_RULE,
        deletion_procedure=ARCHIVE_DELETION_PROCEDURE,
    )
    await deps.registry.save(copy)
    return ArchiveOutcome(archive=copy)


async def read_archive(
    archive_id: str, viewer_id: str, deps: ArchiveDeps, *, is_moderator: bool = False
) -> bytes:
    """Return a copy's text to the person who asked for it or to a moderator.

    Args:
        archive_id: the copy.
        viewer_id: who reads.
        deps: the blob store and registry.
        is_moderator: whether the viewer is a moderator.

    Returns:
        The archived text.

    Raises:
        ArchiveAccessDeniedError: There is no such copy, or the viewer may not see it.

    Features:
        US-KOR-07, F-38
    """
    copy = await deps.registry.get(archive_id)
    if copy is None or not (is_moderator or copy.owner_id == viewer_id):
        raise ArchiveAccessDeniedError
    return await deps.blobs.get(copy.blob_id)


async def delete_archive(
    archive_id: str,
    requester_id: str,
    deps: ArchiveDeps,
    *,
    content_owner: bool = False,
) -> None:
    """Delete a copy on the request of its requester or of the content's owner.

    shortcut: a content owner's identity is vouched for by the caller (the backend
    endpoint), not checked here; add the check when that endpoint exists.

    Args:
        archive_id: the copy.
        requester_id: who asks for the deletion.
        deps: the blob store and registry.
        content_owner: whether the request comes from the page's owner.

    Raises:
        ArchiveAccessDeniedError: There is no such copy, or the requester is
            neither the copy's requester nor the content's owner.

    Features:
        US-KOR-07, F-38
    """
    copy = await deps.registry.get(archive_id)
    if copy is None or not (content_owner or copy.owner_id == requester_id):
        raise ArchiveAccessDeniedError
    await deps.blobs.delete(copy.blob_id)
    await deps.registry.delete(archive_id)
