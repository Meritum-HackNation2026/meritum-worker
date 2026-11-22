"""The organiser's JSON or CSV file on disk, read as raw records.

Features:
    US-KOR-02, F-10, ADR-32
"""

import asyncio
import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path


class OrganiserFile:
    """OrganiserFilePort over a local file (mounted or copied into the worker).

    Features:
        US-KOR-02, F-10, ADR-32
    """

    async def records(  # ruff: ignore[no-self-use]  # OrganiserFilePort is an instance protocol
        self, path: Path
    ) -> list[Mapping[str, object]]:
        """Read the file; validation happens in the import, not here.

        Args:
            path: A ``.json`` or ``.csv`` file, UTF-8 (a BOM is accepted).

        Returns:
            One mapping per record; empty CSV cells are left out.

        Raises:
            ValueError: Another extension, or JSON that holds no list.

        Features:
            US-KOR-02, F-10
        """
        text = await asyncio.to_thread(path.read_text, encoding="utf-8-sig")
        suffix = path.suffix.lower()
        if suffix == ".csv":
            rows = csv.DictReader(io.StringIO(text))
            return [{k: v for k, v in row.items() if k and v} for row in rows]
        if suffix == ".json":
            return _json_records(json.loads(text))
        msg = f"{path.name}: expected .json or .csv"
        raise ValueError(msg)


def _json_records(data: object) -> list[Mapping[str, object]]:
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        data = lists[0] if len(lists) == 1 else None
    if not isinstance(data, list):
        msg = "JSON must be a list of records or an object with one list"
        raise ValueError(msg)  # ruff: ignore[type-check-without-type-error]  # a bad file, not a bad argument type
    return [r for r in data if isinstance(r, dict)]
