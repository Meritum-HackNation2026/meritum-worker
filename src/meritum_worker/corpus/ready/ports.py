"""Where the corpus_ready build reads bronze and writes silver and gold.

Features:
    US-KOR-02, F-12
"""

from collections.abc import Sequence
from typing import Protocol

from meritum_core.corpus.ready import GoldChunk
from meritum_core.shared.embeddings import Vector

from meritum_worker.corpus.ready.models import BronzeDocument, BuildReport


class ReadyStorePort(Protocol):
    """Bronze reads and silver/gold writes of the gold build.

    Features:
        US-KOR-02, F-12
    """

    async def prepare(self) -> None:
        """Apply the corpus_ready migrations; fails when the schema is missing."""
        ...

    async def live_versions(self) -> dict[str, str]:
        """Return ``source_id -> checksum`` of live bronze documents with text."""
        ...

    async def built_versions(self) -> dict[str, str]:
        """Return ``source_id -> checksum`` of the documents silver already has."""
        ...

    async def documents(self, source_ids: Sequence[str]) -> list[BronzeDocument]:
        """Return those live bronze documents with their full text.

        Args:
            source_ids: The documents to read.
        """
        ...

    async def replace(
        self,
        doc: BronzeDocument,
        silver: str,
        chunks: Sequence[tuple[GoldChunk, Vector]],
        build_id: str,
    ) -> None:
        """Replace the document's silver row and gold chunks in one transaction.

        Args:
            doc: The bronze document.
            silver: Its cleaned text.
            chunks: Its gold chunks with their embeddings.
            build_id: The running build.
        """
        ...

    async def remove(self, source_ids: Sequence[str]) -> None:
        """Delete silver and gold of documents no longer live.

        Args:
            source_ids: The documents to forget.
        """
        ...

    async def record(self, report: BuildReport) -> None:
        """Store the build's report in ``corpus_ready.builds``.

        Args:
            report: What the build did.
        """
        ...
