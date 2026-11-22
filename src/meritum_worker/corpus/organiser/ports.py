"""Port of the organiser's files: raw records, validated in the domain.

Features:
    US-KOR-02, F-10, ADR-32
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class OrganiserFilePort(Protocol):
    """Reads one JSON or CSV file the organiser handed over.

    Features:
        US-KOR-02, F-10, ADR-32
    """

    async def records(self, path: Path) -> list[Mapping[str, object]]:
        """Return the file's records as read, before validation.

        Args:
            path: A ``.json`` (a list, or an object with one list) or ``.csv`` file.

        Returns:
            One mapping per record; CSV cells left empty are absent.

        Raises:
            ValueError: The file is neither JSON nor CSV, or holds no list.
        """
        ...
