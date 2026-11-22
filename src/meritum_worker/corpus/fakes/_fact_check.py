"""A fake Fact Check Tools API for tests and behave scenarios, no network.

Features:
    US-KOR-01, F-14, ADR-34
"""

from meritum_worker.corpus.errors import FactCheckUnavailableError
from meritum_worker.corpus.models import FactCheckAnswer


class FakeFactCheck:
    """FactCheckPort that answers every query the same way.

    Args:
        answer: What every search returns; no reviews by default.
        failure: Raised by every search instead, when given.

    Attributes:
        queries: Every query, in order.

    Features:
        US-KOR-01, F-14, ADR-34
    """

    def __init__(
        self,
        answer: FactCheckAnswer | None = None,
        failure: FactCheckUnavailableError | None = None,
    ) -> None:
        self.queries: list[str] = []
        self._answer = answer or FactCheckAnswer()
        self._failure = failure

    async def search(self, query: str, *, language: str) -> FactCheckAnswer:
        """Note the query, then return the answer or raise the failure.

        Args:
            query: The masked claim.
            language: The claim's language; unused.

        Returns:
            The answer given at construction.

        Raises:
            FactCheckUnavailableError: The failure given at construction.
        """  # ruff: ignore[docstring-extraneous-exception]  # the stored instance
        del language
        self.queries.append(query)
        if self._failure is not None:
            raise self._failure
        return self._answer
