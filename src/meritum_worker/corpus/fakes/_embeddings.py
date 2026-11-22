"""Fake embeddings with vectors given per text, for tests and behave scenarios.

Features:
    US-KOR-01, F-14, ADR-34
"""

from collections.abc import Mapping, Sequence

from meritum_core.shared.embeddings import EmbeddingsUnavailableError, Vector


class FakeEmbeddings:
    """EmbeddingsPort that looks each text up in a table.

    Args:
        vectors: The vector of each known text; all of one size.
        failure: Raised by every call instead, when given.

    A text missing from the table gets the zero vector, similar to nothing.

    Features:
        US-KOR-01, F-14, ADR-34
    """

    def __init__(
        self,
        vectors: Mapping[str, Vector],
        failure: EmbeddingsUnavailableError | None = None,
    ) -> None:
        self._vectors = dict(vectors)
        size = len(next(iter(self._vectors.values()), ()))
        self._zero: Vector = (0.0,) * size
        self._failure = failure

    async def embed_query(self, text: str) -> Vector:
        """Look one text up.

        Args:
            text: Any text.

        Returns:
            Its vector from the table.

        Raises:
            EmbeddingsUnavailableError: The failure given at construction.
        """  # ruff: ignore[docstring-extraneous-exception]  # the stored instance
        if self._failure is not None:
            raise self._failure
        return self._vectors.get(text, self._zero)

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Look each text up.

        Args:
            texts: Any texts.

        Returns:
            One vector per text.
        """
        return [await self.embed_query(text) for text in texts]
