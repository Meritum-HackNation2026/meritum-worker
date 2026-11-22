import asyncio
from datetime import UTC, datetime
from typing import Any

from meritum_core.corpus.fetching import FetchedPage, FetchFailureReason, LoginWallError
from meritum_core.jobs.contracts import ARCHIVE_PAGE
from meritum_core.shared.blobs import BlobProvider, BlobSettings
from meritum_core.shared.database import DatabaseSettings

from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus import ArchiveDeps, run_archive_page
from meritum_worker.corpus.adapters import build_archive_deps
from meritum_worker.corpus.fakes import MemoryArchiveRegistry

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
ARCHIVE_ID = "0123456789abcdef0123456789abcdef"
URL = "https://www.gov.pl/web/rcb"
PAGE = FetchedPage(url=URL, content_type="text/html", untrusted_text="RCB ostrzega.")


def _payload() -> dict[str, Any]:
    job = ARCHIVE_PAGE.input(archive_id=ARCHIVE_ID, url=URL, owner_id="citizen-1")
    return job.model_dump(mode="json")


def _deps(answer: FetchedPage | LoginWallError) -> ArchiveDeps:
    memory = build_archive_deps(
        DatabaseSettings(), BlobSettings(provider=BlobProvider.MEMORY)
    )
    return ArchiveDeps(
        pages=FakePageFetcher(answer),
        blobs=memory.blobs,
        registry=MemoryArchiveRegistry(),
    )


def test_the_copy_is_stored_under_the_id_the_backend_chose() -> None:
    deps = _deps(PAGE)
    output = asyncio.run(run_archive_page(_payload(), deps, now=NOW))
    result = ARCHIVE_PAGE.output.model_validate(output)
    assert result.archive_id == ARCHIVE_ID
    assert result.owner_id == "citizen-1"
    assert result.sha256 is not None
    assert result.refusal is None
    saved = asyncio.run(deps.registry.get(ARCHIVE_ID))
    assert saved is not None
    assert saved.sha256 == result.sha256


def test_a_refusal_keeps_the_id_and_the_message() -> None:
    deps = _deps(LoginWallError(FetchFailureReason.LOGIN_WALL))
    output = asyncio.run(run_archive_page(_payload(), deps, now=NOW))
    result = ARCHIVE_PAGE.output.model_validate(output)
    assert result.archive_id == ARCHIVE_ID
    assert result.refusal == "login_wall"
    assert result.message is not None
    assert asyncio.run(deps.registry.get(ARCHIVE_ID)) is None
