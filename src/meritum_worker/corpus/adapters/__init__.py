"""Adapters of the corpus slice: the EUvsDisinfo MCP client, the memory copy and
the migrations of the shared corpus schema.

Features:
    US-KOR-08, US-KOR-02, F-11, F-12, ADR-32
"""

from ._mcp import McpEuvsDisinfo
from ._memory import MemoryEuvsCopy
from ._migrations import apply_corpus_migrations

__all__ = ["McpEuvsDisinfo", "MemoryEuvsCopy", "apply_corpus_migrations"]
