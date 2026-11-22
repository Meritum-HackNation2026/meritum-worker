"""Adapters of the corpus slice: EUvsDisinfo, catalogue documents, migrations.

Features:
    US-KOR-08, US-KOR-02, US-KOR-03, F-11, F-12, F-13, ADR-32
"""

from ._entry_pages import EntryPageDiscovery
from ._fact_check import GoogleFactCheck
from ._feed_discovery import FeedDiscovery
from ._feed_transport import FeedTransport
from ._json_transport import JsonAsTextTransport, build_api_fetcher
from ._mcp import McpEuvsDisinfo
from ._memory import MemoryEuvsCopy
from ._memory_archive import MemoryArchiveRegistry
from ._memory_corpus import MemoryCorpusWriter
from ._migrations import apply_corpus_migrations
from ._openrouter_ranking import OpenRouterReranker
from ._organiser_file import OrganiserFile
from ._postgres import PostgresEuvsCopy
from ._postgres_corpus import PostgresCorpusWriter
from ._postgres_retention import PostgresCorpusRetention
from ._retention_factory import build_corpus_retention
from ._vertex_ranking import VertexReranker
from ._workers_ai_ranking import WorkersAiReranker

__all__ = [
    "EntryPageDiscovery",
    "FeedDiscovery",
    "FeedTransport",
    "GoogleFactCheck",
    "JsonAsTextTransport",
    "McpEuvsDisinfo",
    "MemoryArchiveRegistry",
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
    "build_api_fetcher",
    "build_corpus_retention",
]
