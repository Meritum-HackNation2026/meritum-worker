"""The local copy of the official EU sanctions list and the warning drawn from it.

The warning is a neutral note about the source's context. It never touches the
verdict, and only a current entry that can be checked at its ``basis_url``
produces one.

Features:
    US-ZRD-07, F-34
"""

from collections.abc import Awaitable, Callable, Mapping
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from meritum_core.checks.contracts import SourceStatusWarning
from pydantic import BaseModel, ConfigDict, HttpUrl, ValidationError


class SanctionedEntity(BaseModel):
    """One entry of the EU list that names web domains.

    Attributes:
        entity: the listed entity's name.
        domains: the entity's domains, lowercase, without ``www.``.
        basis_url: the link to the entry in the official list.
        listed_on: the day the entry took effect.
        delisted_on: the day it stopped applying, if it did.

    Features:
        US-ZRD-07, F-34
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: str
    domains: tuple[str, ...]
    basis_url: HttpUrl
    listed_on: date
    delisted_on: date | None = None

    def is_current(self, on: date) -> bool:
        """Whether the entry applies on a day.

        Args:
            on: the day, usually the check's receipt day.

        Returns:
            True from ``listed_on`` until ``delisted_on`` (exclusive).
        """
        return self.listed_on <= on and (
            self.delisted_on is None or on < self.delisted_on
        )


class SanctionsList(BaseModel):
    """The local copy of the list; empty until a refresh writes one.

    Attributes:
        entities: the entries.

    Features:
        US-ZRD-07, F-34
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entities: tuple[SanctionedEntity, ...] = ()

    def warning_for(self, link: str, *, on: date) -> SourceStatusWarning | None:
        """Match the link's host, or its parent domain, to a current entry.

        Args:
            link: the checked link.
            on: the day the entry must apply.

        Returns:
            The neutral warning, or None without a current entry.
        """
        try:
            host = (urlsplit(link).hostname or "").removeprefix("www.")
        except ValueError:  # a malformed link matches nothing
            return None
        for entry in self.entities:
            if entry.is_current(on) and any(
                host == d or host.endswith(f".{d}") for d in entry.domains
            ):
                return SourceStatusWarning(
                    code="eu_sanctioned_entity",
                    entity=entry.entity[:120],
                    basis_url=entry.basis_url,
                )
        return None


def load_sanctions(path: Path) -> SanctionsList:
    """Read the local copy.

    Args:
        path: the JSON file.

    Returns:
        The list.

    Raises:
        ValueError: the file is not a valid list.

    Features:
        US-ZRD-07, F-34
    """
    try:
        return SanctionsList.model_validate_json(path.read_bytes())
    except ValidationError as error:
        raise ValueError(str(error)) from error


def sanctions_from_env(env: Mapping[str, str]) -> SanctionsList:
    """Load the copy named by ``MERITUM_SANCTIONS_LIST_PATH``; empty without one.

    Args:
        env: the worker's environment.

    Returns:
        The list, empty when the variable or the file is missing.

    Features:
        US-ZRD-07, F-34
    """
    path = Path(env.get("MERITUM_SANCTIONS_LIST_PATH", ""))
    return load_sanctions(path) if path.is_file() else SanctionsList()


async def refresh_sanctions(
    download: Callable[[], Awaitable[bytes]], path: Path
) -> int:
    """Replace the local copy with a freshly downloaded, valid list.

    A download that fails validation leaves the copy as it was.

    Args:
        download: reads the official list's JSON export.
        path: where the copy lives.

    Returns:
        How many entries the new copy holds.

    Raises:
        ValueError: the download is not a valid list; nothing is written.

    Features:
        US-ZRD-07, F-34
    """
    body = await download()
    try:
        fresh = SanctionsList.model_validate_json(body)
    except ValidationError as error:
        raise ValueError(str(error)) from error
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(body)
    tmp.replace(path)
    return len(fresh.entities)
