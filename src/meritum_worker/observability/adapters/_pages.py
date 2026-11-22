"""PageFetcherPort that records fetched pages or replays them from a cassette.

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-27, ADR-28
"""

import asyncio
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    PageFetcherPort,
    PageFetchError,
)

from meritum_worker.observability.adapters._tape import Tape
from meritum_worker.observability.cassette import Cassette, PageTake


def _now() -> datetime:
    return datetime.now(UTC)


class CassettePages:
    """Records each fetch of ``fetcher``, or replays them when it is None.

    Args:
        cassette: Where pages are recorded or read from.
        fetcher: The SSRF-safe fetcher to record; None replays without network.
        clock: When a recorded page counts as fetched.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-27, ADR-28
    """

    def __init__(
        self,
        cassette: Cassette,
        fetcher: PageFetcherPort | None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._tape = Tape(cassette.pages)
        self._fetcher = fetcher
        self._clock = clock

    @staticmethod
    def key(url: str, purpose: FetchPurpose) -> str:
        """The request key of a fetch, also the document id in the manifest.

        Args:
            url: The requested URL.
            purpose: Why it is fetched.

        Returns:
            The hex SHA-256 of the purpose and URL.
        """
        return hashlib.sha256(f"{purpose.value} {url}".encode()).hexdigest()

    async def fetch(self, url: str, *, purpose: FetchPurpose) -> FetchedPage:
        """Fetch through the fetcher (recording it) or answer from the cassette.

        Args:
            url: An absolute http(s) URL.
            purpose: Why it is fetched.

        Returns:
            The page's main text, marked as untrusted data.

        Raises:
            PageFetchError: The fetch failed, now or when recorded.
            CassetteMissError: Replay found no recorded fetch of this URL.
            CancelledError: The caller's deadline cut the call off while recording.
            TimeoutError: The recorded call was cut off by the same deadline.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by Tape.next
        key = self.key(url, purpose)
        if self._fetcher is None:
            return self._replay(key)
        fetched_at = self._clock()
        try:
            page = await self._fetcher.fetch(url, purpose=purpose)
        except asyncio.CancelledError:
            # The caller's deadline cut the call off; replay raises TimeoutError.
            self._tape.record_timeout(key)
            raise
        except PageFetchError as error:
            self._tape.record(key, PageTake(reason=error.reason, fetched_at=fetched_at))
            raise
        self._tape.record(key, PageTake(page=page, fetched_at=fetched_at))
        return page

    def _replay(self, key: str) -> FetchedPage:
        take = self._tape.next(key)
        if take.page is None:
            raise PageFetchError(take.reason or FetchFailureReason.UNREACHABLE)
        return take.page
