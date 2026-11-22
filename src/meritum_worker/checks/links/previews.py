"""Read the title and description a video or social service publishes for previews.

Features:
    US-SPR-07, F-06, ADR-12
"""

import json
from html.parser import HTMLParser
from typing import override

from meritum_worker.checks.links.constants import (
    FULL_DESCRIPTION,
    LOGIN_FORM,
    OG_DESCRIPTION,
    OG_TITLE,
    PREVIEW_DOMAINS,
)


class _OpenGraph(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.found: dict[str, str] = {}

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        meta = dict(attrs)
        name, content = meta.get("property") or "", (meta.get("content") or "").strip()
        if name in {OG_TITLE, OG_DESCRIPTION} and content:
            self.found.setdefault(name, content)


def is_preview_host(host: str | None) -> bool:
    """Whether the host is a video or social service read from its preview data.

    Args:
        host: a host name, with or without a port; None for no host.

    Returns:
        True for a domain in ``PREVIEW_DOMAINS`` and its subdomains.

    Features:
        US-SPR-07, F-06
    """
    name = (host or "").lower().partition(":")[0]
    return any(name == d or name.endswith(f".{d}") for d in PREVIEW_DOMAINS)


def preview_text(html: str) -> str:
    """Return the title and description the page publishes, as plain text.

    The Open Graph title and description are what the service shows in link
    previews. YouTube cuts its description there, so the whole one is read from
    the page's data when it is present.

    Args:
        html: the page of a video or a post (untrusted).

    Returns:
        The title, a blank line and the description; empty when the page has
        no title or is a login form, so nothing public can be read.

    Features:
        US-SPR-07, F-06, ADR-12
    """
    reader = _OpenGraph()
    reader.feed(html)
    title = reader.found.get(OG_TITLE, "")
    if not title or LOGIN_FORM.search(html):
        return ""
    description = _full_description(html) or reader.found.get(OG_DESCRIPTION, "")
    return "\n\n".join(part for part in (title, description.strip()) if part)


def _full_description(html: str) -> str:
    found = FULL_DESCRIPTION.search(html)
    try:
        return str(json.loads(found.group(1))) if found else ""
    except ValueError:  # not a JSON string after all: the Open Graph one stays
        return ""
