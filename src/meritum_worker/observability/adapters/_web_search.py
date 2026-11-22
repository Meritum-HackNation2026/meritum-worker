"""WebSearchPort that records a search provider's answers or replays them.

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-28
"""

import asyncio
import hashlib

from meritum_core.corpus.web_search import (
    WebSearchCandidate,
    WebSearchError,
    WebSearchPort,
    WebSearchRateLimitError,
    WebSearchTimeoutError,
    WebSearchUnavailableError,
)
from meritum_core.corpus.web_search.constants import DEFAULT_RESULTS
from meritum_core.security import MaskedText

from meritum_worker.observability.adapters._tape import Tape
from meritum_worker.observability.cassette import Cassette, SearchTake


def _failure(name: str) -> type[WebSearchError]:
    known = (WebSearchRateLimitError, WebSearchTimeoutError, WebSearchUnavailableError)
    return next((e for e in known if e.__name__ == name), WebSearchUnavailableError)


class CassetteWebSearch:
    """Records each answer of ``search``, or replays them when it is None.

    Args:
        cassette: Where answers are recorded or read from.
        search: The catalogue-filtered search to record; None replays without
            keys or network.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    def __init__(self, cassette: Cassette, search: WebSearchPort | None) -> None:
        self._tape = Tape(cassette.web_search)
        self._search = search

    async def search(
        self, query: MaskedText, *, limit: int = DEFAULT_RESULTS
    ) -> list[WebSearchCandidate]:
        """Search through the provider (recording it) or answer from the cassette.

        Args:
            query: The claim with personal data masked.
            limit: Addresses asked from the provider.

        Returns:
            Catalogue candidates in the provider's order.

        Raises:
            WebSearchError: The search failed, now or when recorded, with the
                same error type.
            CassetteMissError: Replay found no recorded answer for this query.
            CancelledError: The caller's deadline cut the call off while recording.
            TimeoutError: The recorded call was cut off by the same deadline.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by Tape.next
        key = hashlib.sha256(f"{limit} {query.text}".encode()).hexdigest()
        if self._search is None:
            take = self._tape.next(key)
            if take.failure is not None:
                raise _failure(take.failure)(key)
            return list(take.candidates)
        try:
            candidates = await self._search.search(query, limit=limit)
        except asyncio.CancelledError:
            # The caller's deadline cut the call off; replay raises TimeoutError.
            self._tape.record_timeout(key)
            raise
        except WebSearchError as error:
            self._tape.record(key, SearchTake(failure=type(error).__name__))
            raise
        self._tape.record(key, SearchTake(candidates=tuple(candidates)))
        return candidates
