"""A fake live web search for tests and behave scenarios, no network.

Features:
    US-KOR-04, US-SPR-02, F-09, F-13
"""

import asyncio

from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.pii import MaskedText


class FakeWebSearch:
    """WebSearchPort that finds the same candidates for every query.

    Args:
        candidates: what every search returns; none by default.

    Attributes:
        queries: the text of every query, in order.
        most_at_once: the most searches that were running at the same time.

    Features:
        US-KOR-04, US-SPR-02, F-09, F-13
    """

    def __init__(self, candidates: tuple[WebSearchCandidate, ...] = ()) -> None:
        self.queries: list[str] = []
        self.most_at_once = 0
        self._candidates = candidates
        self._running = 0

    async def search(
        self, query: MaskedText, *, limit: int = 10
    ) -> list[WebSearchCandidate]:
        """Note the query, yield once so parallel searches overlap, return candidates.

        Args:
            query: the masked claim.
            limit: most candidates returned.

        Returns:
            The first ``limit`` candidates given at construction.
        """
        self.queries.append(query.text)
        self._running += 1
        self.most_at_once = max(self.most_at_once, self._running)
        await asyncio.sleep(0)
        self._running -= 1
        return list(self._candidates[:limit])
