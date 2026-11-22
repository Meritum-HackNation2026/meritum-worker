"""The corpus snapshot an embeddings comparison searches (US-OBS-04, worker#113).

A comparison re-embeds every passage with each candidate, so it reads the
snapshot's passages and their documents' URLs, not the stored vectors.

Features:
    US-WDR-02, US-OBS-04, F-12, F-27, ADR-19
"""

import math
from collections.abc import Sequence
from itertools import batched
from pathlib import Path
from typing import Protocol

from meritum_core.corpus import Passage
from meritum_core.shared.embeddings import EmbeddingsPort, Vector
from pydantic import AwareDatetime, BaseModel, ConfigDict

from meritum_worker.observability.constants import EMBED_BATCH


class SnapshotCorpus(BaseModel):
    """Every passage a ``corpus_version`` sees, with its documents' URLs.

    Attributes:
        version: The ``corpus_version``, e.g. ``2026-11-22T04:00Z``.
        taken_at: When the snapshot was taken; passage age counts from it.
        urls: Document URL per source id.
        passages: The passages the snapshot sees.

    Features:
        US-WDR-02, US-OBS-04, F-12, F-27, ADR-19
    """

    model_config = ConfigDict(frozen=True)

    version: str
    taken_at: AwareDatetime
    urls: dict[str, str]
    passages: tuple[Passage, ...]


class SnapshotCorpusPort(Protocol):
    """Reads one snapshot's passages from the corpus store.

    Features:
        US-WDR-02, US-OBS-04, F-12, F-27, ADR-19
    """

    async def read(self, version: str) -> SnapshotCorpus:
        """Return the passages ``version`` sees.

        Args:
            version: The ``corpus_version``.

        Returns:
            The snapshot.

        Raises:
            UnknownCorpusVersionError: No snapshot has this version.
        """
        ...


class MeteredEmbeddings:
    """Embeds each text once, counts the characters sent and unit-normalises.

    The memory search embeds the whole snapshot on every query; with this it
    pays for each passage once, and its dot product is the cosine distance
    pgvector ranks the corpus by.

    Args:
        inner: The candidate's model.

    Attributes:
        characters: Characters sent to ``inner`` so far.

    Features:
        US-WDR-02, US-OBS-04, F-12, F-27
    """

    def __init__(self, inner: EmbeddingsPort) -> None:
        self._inner = inner
        self._vectors: dict[str, Vector] = {}
        self.characters = 0

    async def embed_query(self, text: str) -> Vector:
        """Embed one query, from memory when seen before.

        Args:
            text: The query.

        Returns:
            Its unit vector.
        """
        if text not in self._vectors:
            self._remember([text], [await self._inner.embed_query(text)])
        return self._vectors[text]

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Embed the texts not seen before, ``EMBED_BATCH`` per call.

        Args:
            texts: The passages.

        Returns:
            One unit vector per text.
        """
        missing = dict.fromkeys(t for t in texts if t not in self._vectors)
        for chunk in batched(missing, EMBED_BATCH, strict=False):
            self._remember(chunk, await self._inner.embed_documents(chunk))
        return [self._vectors[text] for text in texts]

    def _remember(self, texts: Sequence[str], vectors: Sequence[Vector]) -> None:
        for text, vector in zip(texts, vectors, strict=True):
            norm = math.hypot(*vector) or 1.0
            self._vectors[text] = tuple(x / norm for x in vector)
            self.characters += len(text)


def load_snapshot_file(path: Path) -> SnapshotCorpus:
    """Read a snapshot saved as JSON, for runs without the corpus database.

    Args:
        path: A ``SnapshotCorpus`` as JSON.

    Returns:
        The validated snapshot; invalid JSON or fields fail while parsing.

    Features:
        US-WDR-02, US-OBS-04, F-12, F-27, ADR-19
    """
    return SnapshotCorpus.model_validate_json(path.read_text(encoding="utf-8"))
