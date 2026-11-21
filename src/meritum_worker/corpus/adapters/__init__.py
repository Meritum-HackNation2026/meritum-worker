"""Adapters of the corpus slice: EUvsDisinfo client, local copies, migrations.

Features:
    US-KOR-08, US-KOR-02, F-11, F-12, ADR-32
"""

from ._mcp import McpEuvsDisinfo
from ._memory import MemoryEuvsCopy
from ._migrations import apply_corpus_migrations
from ._postgres import PostgresEuvsCopy
from ._vertex_ranking import VertexReranker
from ._workers_ai_ranking import WorkersAiReranker

__all__ = [
    "McpEuvsDisinfo",
    "MemoryEuvsCopy",
    "PostgresEuvsCopy",
    "VertexReranker",
    "WorkersAiReranker",
    "apply_corpus_migrations",
]
