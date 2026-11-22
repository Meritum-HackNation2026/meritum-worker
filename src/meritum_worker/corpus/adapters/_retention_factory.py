"""Builds the corpus side of the retention and publisher removal workflows.

Features:
    US-KOR-05, F-10, ADR-13
"""

from meritum_core.corpus import CorpusProvider, CorpusSettings

from meritum_worker.corpus.removals import CorpusRetentionPort

from ._memory_corpus import MemoryCorpusWriter
from ._postgres_retention import PostgresCorpusRetention


def build_corpus_retention(
    settings: CorpusSettings | None = None,
) -> CorpusRetentionPort:
    """Build the corpus retention the settings name.

    Args:
        settings: As for ``build_corpus_writer``; None or memory: an empty corpus.

    Returns:
        The PostgreSQL retention or an in-memory writer.

    Raises:
        ValueError: postgres without a database URL (settings built unvalidated).

    Features:
        US-KOR-05, F-10, ADR-13
    """
    if settings is None or settings.provider is CorpusProvider.MEMORY:
        return MemoryCorpusWriter()
    if settings.database_url is None:
        msg = "MERITUM_CORPUS_DATABASE_URL is required for postgres"
        raise ValueError(msg)
    return PostgresCorpusRetention(settings.database_url.get_secret_value())
