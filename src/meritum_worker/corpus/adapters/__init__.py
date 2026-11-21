"""Adapters of the corpus slice: the EUvsDisinfo MCP client and the memory copy.

Features:
    US-KOR-08, F-11
"""

from ._mcp import McpEuvsDisinfo
from ._memory import MemoryEuvsCopy

__all__ = ["McpEuvsDisinfo", "MemoryEuvsCopy"]
