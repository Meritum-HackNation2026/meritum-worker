"""In-memory corpus_ready store: the fake for tests, behave and memory runs.

Features:
    US-KOR-02, F-12
"""

from collections.abc import Iterable, Sequence

from meritum_core.corpus.ready import GoldChunk
from meritum_core.shared.embeddings import Vector

from meritum_worker.corpus.ready.models import BronzeDocument, BuildReport


class MemoryReadyStore:
    """ReadyStorePort over dicts; ``bronze`` holds the live documents.

    Args:
        bronze: The live bronze documents.

    Features:
        US-KOR-02, F-12
    """

    def __init__(self, bronze: Iterable[BronzeDocument] = ()) -> None:
        self.bronze = {d.source_id: d for d in bronze}
        self.silver: dict[str, tuple[str, str]] = {}
        self.gold: dict[str, list[tuple[GoldChunk, Vector]]] = {}
        self.reports: list[BuildReport] = []
        self.prepared = False

    async def prepare(self) -> None:
        """Nothing to migrate in memory."""
        self.prepared = True

    async def live_versions(self) -> dict[str, str]:
        """Live bronze versions.

        Returns:
            ``source_id -> checksum``.
        """
        return {sid: d.checksum for sid, d in self.bronze.items()}

    async def built_versions(self) -> dict[str, str]:
        """Silver versions.

        Returns:
            ``source_id -> checksum``.
        """
        return {sid: checksum for sid, (checksum, _) in self.silver.items()}

    async def documents(self, source_ids: Sequence[str]) -> list[BronzeDocument]:
        """The live documents asked for.

        Args:
            source_ids: The documents to read.

        Returns:
            Those that are live.
        """
        return [self.bronze[s] for s in source_ids if s in self.bronze]

    async def replace(
        self,
        doc: BronzeDocument,
        silver: str,
        chunks: Sequence[tuple[GoldChunk, Vector]],
        build_id: str,  # ruff: ignore[unused-method-argument]  # the memory store keeps no build ids
    ) -> None:
        """Replace one document's silver and gold.

        Args:
            doc: The bronze document.
            silver: Its cleaned text.
            chunks: Its gold chunks with embeddings.
            build_id: The running build.
        """
        self.silver[doc.source_id] = (doc.checksum, silver)
        self.gold[doc.source_id] = list(chunks)

    async def remove(self, source_ids: Sequence[str]) -> None:
        """Forget documents.

        Args:
            source_ids: The documents to forget.
        """
        for sid in source_ids:
            self.silver.pop(sid, None)
            self.gold.pop(sid, None)

    async def record(self, report: BuildReport) -> None:
        """Keep the report.

        Args:
            report: What the build did.
        """
        self.reports.append(report)
