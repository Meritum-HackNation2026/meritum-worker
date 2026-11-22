"""Read the European Commission's Financial Sanctions Files export (XML 1.1).

The official consolidated list is published on data.europa.eu as
``xmlFullSanctionsList_1_1``. Only entities with a website in
``<contactInfo key="WEB">`` can be matched to a link, so only they are kept.
The export lists current entries only: a delisted entity disappears from it.

Features:
    US-ZRD-07, F-34
"""

import io
import re
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element  # nosec B405  # ruff: ignore[suspicious-xml-etree-import]  # type only; defusedxml parses

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, iterparse
from pydantic import ValidationError

from meritum_worker.evidence.constants import (
    FSF_INVALID,
    FSF_NAMESPACE,
    SANCTIONS_EMPTY,
    SHARED_PLATFORM_HOSTS,
    WEBSITE_HOST,
    WEBSITE_NOISE,
)
from meritum_worker.evidence.sanctions import SanctionedEntity, SanctionsList


def _host(token: str) -> str:
    """Read the bare host of one website token.

    Args:
        token: e.g. ``https://www.niruco.com/`` or ``beget.ru``.

    Returns:
        The host without ``www.``; empty for a page on a site (it has a
        path), a shared platform, or a word that is not a domain.
    """
    url = token.lower().replace("htps://", "https://")
    if "://" not in url:
        url = f"http://{url}"
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").removeprefix("www.")
    except ValueError:
        return ""
    if parts.path.strip("/") or parts.query or not WEBSITE_HOST.match(host):
        return ""
    return "" if host in SHARED_PLATFORM_HOSTS else host


def website_domains(value: str) -> list[str]:
    """Split one ``WEB`` value into the domains it names.

    A part with a word that is not a domain (``beget kz.com``) is dropped whole
    rather than guessed at.

    Args:
        value: the attribute, e.g. ``" www.nirubattery.com; www.niruco.com"``.

    Returns:
        The domains, lowercase, without ``www.``.

    Features:
        US-ZRD-07, F-34
    """
    found: list[str] = []
    for part in re.split(r"[;,]", value):
        words = [w for w in part.split() if w.lower() not in WEBSITE_NOISE]
        hosts = [_host(w) for w in words]
        found += [h for h in hosts if h and h not in found] if all(hosts) else []
    return found


def _entity(node: Element) -> SanctionedEntity | None:
    """Turn one ``sanctionEntity`` into an entry.

    Args:
        node: the element, with its children.

    Returns:
        The entry, or None when it names no website.
    """
    values = [
        info.get("value", "")
        for info in node.iter(f"{FSF_NAMESPACE}contactInfo")
        if info.get("key") == "WEB"
    ]
    domains = list(dict.fromkeys(d for v in values for d in website_domains(v)))
    names = node.findall(f"{FSF_NAMESPACE}nameAlias")
    regulation = node.find(f"{FSF_NAMESPACE}regulation")
    if not domains or not names or regulation is None:
        return None
    english = [n for n in names if n.get("nameLanguage", "") in {"", "EN"}]
    listed = node.get("designationDate") or regulation.get("entryIntoForceDate", "")
    act = regulation.findtext(f"{FSF_NAMESPACE}publicationUrl", "").strip()
    return SanctionedEntity.model_validate(
        {
            "entity": (english or names)[0].get("wholeName", "").strip(),
            "domains": tuple(domains),
            "basis_url": act,
            "listed_on": date.fromisoformat(listed),
        }
    )


def parse_fsf_export(body: bytes) -> SanctionsList:
    """Turn the FSF XML 1.1 export into the local copy's list.

    Args:
        body: the downloaded export (about 26 MB), parsed as it streams.

    Returns:
        The entities that name at least one website.

    Raises:
        ValueError: the XML is malformed, has a DTD or entities, or an entry
            that names a website lacks a valid date or act link.

    Features:
        US-ZRD-07, F-34
    """
    entities: list[SanctionedEntity] = []
    try:
        for _, node in iterparse(io.BytesIO(body), forbid_dtd=True):
            if node.tag != f"{FSF_NAMESPACE}sanctionEntity":
                continue
            entry = _entity(node)
            entities += [entry] if entry is not None else []
            node.clear()
    except (ParseError, DefusedXmlException, ValidationError) as error:
        message = f"{FSF_INVALID}: {error}"
        raise ValueError(message) from error
    return SanctionsList(entities=tuple(entities))


def _fresh_list(body: bytes) -> tuple[SanctionsList, bytes]:
    """Validate a download and give the bytes of the copy to write.

    Args:
        body: the FSF XML export, or a list already in the copy's JSON format.

    Returns:
        The list and the JSON copy.

    Raises:
        ValueError: the download is not a valid list or has no entity.
    """
    if body.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<"):
        fresh = parse_fsf_export(body)
        copy = fresh.model_dump_json(indent=1).encode()
    else:
        try:
            fresh = SanctionsList.model_validate_json(body)
        except ValidationError as error:
            raise ValueError(str(error)) from error
        copy = body
    if not fresh.entities:
        raise ValueError(SANCTIONS_EMPTY)
    return fresh, copy


async def refresh_sanctions(
    download: Callable[[], Awaitable[bytes]], path: Path
) -> int:
    """Replace the local copy with a freshly downloaded, valid list.

    The download is the official FSF XML export, or a list already in the
    copy's JSON format. One that fails validation, or names no entity with a
    website, raises ``ValueError`` from ``_fresh_list`` and writes nothing.

    Args:
        download: reads the official export.
        path: where the JSON copy lives.

    Returns:
        How many entries the new copy holds.

    Features:
        US-ZRD-07, F-34
    """
    fresh, copy = _fresh_list(await download())
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(copy)
    tmp.replace(path)
    return len(fresh.entities)
