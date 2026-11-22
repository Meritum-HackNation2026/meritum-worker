"""In-memory results and scripted embeddings for tests and behave.

Features:
    US-MOD-02, F-24
"""

from collections.abc import Mapping, Sequence
from datetime import datetime

from meritum_core.shared.embeddings import EmbeddingsSettings, Vector, build_embeddings

from meritum_worker.moderation.models import PastClaim


class InMemoryCheckResults:
    """CheckResults fake: finished checks added by hand.

    Features:
        US-MOD-01, US-MOD-02, F-24
    """

    def __init__(self) -> None:
        self._claims: dict[str, list[tuple[str, bool]]] = {}
        self._started: dict[str, datetime] = {}

    def add(
        self, check_id: str, started: datetime, claims: Sequence[tuple[str, bool]]
    ) -> None:
        """Add a finished check.

        Args:
            check_id: its id.
            started: when it started.
            claims: each claim with whether it is unanswered.
        """
        self._claims[check_id] = list(claims)
        self._started[check_id] = started

    async def claim(self, check_id: str, claim_index: int) -> str | None:
        """Read one claim.

        Args:
            check_id: the check.
            claim_index: the position.

        Returns:
            The claim text, or None.
        """
        claims = self._claims.get(check_id, [])
        return claims[claim_index][0] if claim_index < len(claims) else None

    async def unanswered_since(self, since: datetime) -> list[PastClaim]:
        """List unanswered claims of checks started after ``since``, latest first.

        Args:
            since: the window's start.

        Returns:
            The claims.
        """
        ids = sorted(self._started, key=self._started.__getitem__, reverse=True)
        return [
            PastClaim(i, text)
            for i in ids
            if self._started[i] > since
            for text, unanswered in self._claims[i]
            if unanswered
        ]


class ScriptedEmbeddings:
    """Embeddings that give chosen texts chosen vectors and the stub's for the rest.

    Args:
        vectors: the vector of each scripted text.

    Features:
        US-MOD-02, F-24
    """

    def __init__(self, vectors: Mapping[str, Vector]) -> None:
        self._vectors = dict(vectors)
        self._stub = build_embeddings(EmbeddingsSettings())

    async def embed_query(self, text: str) -> Vector:
        """Embed one text.

        Args:
            text: the text.

        Returns:
            Its scripted or stub vector.
        """
        return self._vectors.get(text) or await self._stub.embed_query(text)

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Embed texts in order.

        Args:
            texts: the texts.

        Returns:
            One vector per text.
        """
        return [await self.embed_query(t) for t in texts]
