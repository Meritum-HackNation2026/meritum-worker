"""Steps of the page archiving scenarios in features/corpus.feature.

They run on the fake page fetcher, the in-memory blob store and archive registry;
no network, no database.
"""

import asyncio
from datetime import UTC, datetime

from behave import given, then, when
from behave.runner import Context
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    LoginWallError,
    PageFetchError,
)
from meritum_core.shared.blobs import (
    BlobNotFoundError,
    BlobProvider,
    BlobSettings,
    build_blob_store,
)

from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus import (
    ARCHIVE_RATE_LIMIT,
    ArchiveAccessDeniedError,
    ArchiveDeps,
    ArchiveRefusal,
    ArchiveRequest,
    archive_page,
    delete_archive,
    read_archive,
)
from meritum_worker.corpus.fakes import MemoryArchiveRegistry, MemoryCorpusWriter

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
URL = "https://www.gov.pl/web/rcb/ostrzezenie-przed-burzami"
OWNER, STRANGER, MODERATOR = "citizen-1", "citizen-2", "moderator-1"
SHA256_HEX = 64
PAGE = FetchedPage(url=URL, content_type="text/html", untrusted_text="RCB ostrzega.")


def _deps(context: Context, answer: FetchedPage | PageFetchError) -> None:
    context.pages = FakePageFetcher(answer)
    context.blobs = build_blob_store(BlobSettings(provider=BlobProvider.MEMORY))
    context.registry = MemoryArchiveRegistry()
    context.corpus = MemoryCorpusWriter()
    context.deps = ArchiveDeps(
        pages=context.pages, blobs=context.blobs, registry=context.registry
    )


def _archive(context: Context) -> None:
    request = ArchiveRequest(url=URL, owner_id=OWNER)
    context.outcome = asyncio.run(archive_page(request, context.deps, now=NOW))


@given("obywatel prosi o archiwizację publicznej strony gov.pl")
def public_page(context: Context) -> None:
    _deps(context, PAGE)


@given("obywatel prosi o archiwizację posta, który wymaga logowania")
def login_wall(context: Context) -> None:
    _deps(context, LoginWallError(FetchFailureReason.LOGIN_WALL))


@given("obywatel prosi o archiwizację strony, której robots.txt zabrania pobierania")
def robots_denied(context: Context) -> None:
    _deps(context, PageFetchError(FetchFailureReason.ROBOTS_DISALLOWED))


@given("obywatel, który wykorzystał limit próśb o archiwizację")
def over_limit(context: Context) -> None:
    _deps(context, PAGE)
    for _ in range(ARCHIVE_RATE_LIMIT):
        _archive(context)
        assert context.outcome.archive is not None


@given("obywatel ma zarchiwizowaną stronę gov.pl")
def archived_page(context: Context) -> None:
    _deps(context, PAGE)
    _archive(context)


@when("workflow archiwizacji kończy się")
@when("workflow archiwizacji działa")
@when("prosi o kolejną archiwizację")
def archiving_runs(context: Context) -> None:
    _archive(context)


@when("zlecający prosi o usunięcie kopii")
def owner_deletes(context: Context) -> None:
    context.archive_id = context.outcome.archive.archive_id
    context.blob_id = context.outcome.archive.blob_id
    asyncio.run(delete_archive(context.archive_id, OWNER, context.deps))


@then(
    "kopia ma zapisaną podstawę prawną, retencję, kontrolę dostępu"
    " i procedurę usunięcia"
)
def copy_has_terms(context: Context) -> None:
    copy = context.outcome.archive
    assert copy is not None
    assert copy.legal_basis
    assert copy.expires_at > copy.archived_at
    assert copy.access_rule
    assert copy.deletion_procedure
    assert len(copy.sha256) == SHA256_HEX
    assert context.pages.calls == [(URL, FetchPurpose.SOURCE)]


@then(
    "widzi ją tylko ta osoba i moderatorzy,"
    " a kopia nie trafia do korpusu ani do odpowiedzi dla innych"
)
def only_owner_and_moderators(context: Context) -> None:
    copy = context.outcome.archive
    for viewer in (OWNER, MODERATOR):
        data = asyncio.run(
            read_archive(
                copy.archive_id,
                viewer,
                context.deps,
                is_moderator=viewer == MODERATOR,
            )
        )
        assert b"RCB ostrzega." in data
    try:
        asyncio.run(read_archive(copy.archive_id, STRANGER, context.deps))
    except ArchiveAccessDeniedError:
        pass
    else:
        msg = "a stranger read the copy"
        raise AssertionError(msg)
    assert asyncio.run(context.corpus.documents()) == []


@then("kopia nie powstaje, a obywatel dostaje komunikat")
def no_copy(context: Context) -> None:
    outcome = context.outcome
    assert outcome.archive is None
    assert isinstance(outcome.refusal, ArchiveRefusal)
    assert outcome.message


@then("kopii nie ma ani w rejestrze, ani w magazynie")
def copy_deleted(context: Context) -> None:
    copy_id = context.archive_id
    assert asyncio.run(context.registry.get(copy_id)) is None
    try:
        asyncio.run(context.blobs.get(context.blob_id))
    except BlobNotFoundError:
        pass
    else:
        msg = "the blob is still stored"
        raise AssertionError(msg)
