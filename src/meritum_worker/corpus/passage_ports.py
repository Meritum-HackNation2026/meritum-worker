"""Port of the corpus documents a check reads for the passages it cites.

Features:
    US-KOR-02, US-ZRD-01, F-12, F-16
"""

from typing import Protocol, runtime_checkable

from meritum_worker.corpus.documents import DocumentMeta


@runtime_checkable
class CorpusDocumentsPort(Protocol):
    """Reads the metadata of corpus documents, for the passages a check cites.

    ``CorpusWriterPort`` has the same method; a check only reads (worker#162).

    Features:
        US-KOR-02, US-ZRD-01, F-12, F-16
    """

    async def document(self, source_id: str) -> DocumentMeta | None:
        """Return one live document's metadata.

        Args:
            source_id: The document.

        Returns:
            The metadata, None when the corpus has no such document.
        """
        ...
