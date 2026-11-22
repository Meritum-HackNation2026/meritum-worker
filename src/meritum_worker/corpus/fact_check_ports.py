"""Port of the fact-check search: the Fact Check Tools API stays in the worker.

Only the worker calls it (ADR-24, ADR-34).

Features:
    US-KOR-01, F-14, ADR-24, ADR-34
"""

from typing import Protocol, runtime_checkable

from meritum_worker.corpus.models import FactCheckAnswer


@runtime_checkable
class FactCheckPort(Protocol):
    """Searches the fact-checkers' ratings in Google Fact Check Tools API.

    Features:
        US-KOR-01, F-14, ADR-24, ADR-34
    """

    async def search(self, query: str, *, language: str) -> FactCheckAnswer:
        """Return the reviews whose claim matches ``query``.

        Args:
            query: The masked claim.
            language: ISO 639-1 code of the claim's language.

        Returns:
            The reviews; none when the index has none.

        Raises:
            FactCheckUnavailableError: The API failed, hit its limit or the key is
                missing or refused.
        """
        ...
