"""Adapters of the corpus slice: EUvsDisinfo, catalogue documents, migrations.

Features:
    US-KOR-08, US-KOR-02, F-11, F-12, ADR-32
"""

from ._entry_pages import EntryPageDiscovery
from ._mcp import McpEuvsDisinfo
from ._memory import MemoryEuvsCopy
from ._memory_corpus import MemoryCorpusWriter
from ._migrations import apply_corpus_migrations
from ._openrouter_ranking import OpenRouterReranker
from ._organiser_file import OrganiserFile
from ._postgres import PostgresEuvsCopy
from ._postgres_corpus import PostgresCorpusWriter
from ._postgres_retention import PostgresCorpusRetention
from ._vertex_ranking import VertexReranker
from ._workers_ai_ranking import WorkersAiReranker

__all__ = [
    "EntryPageDiscovery",
    "McpEuvsDisinfo",
    "MemoryCorpusWriter",
    "MemoryEuvsCopy",
    "OpenRouterReranker",
    "OrganiserFile",
    "PostgresCorpusRetention",
    "PostgresCorpusWriter",
    "PostgresEuvsCopy",
    "VertexReranker",
    "WorkersAiReranker",
    "apply_corpus_migrations",
]
