"""Discovery by entry page: each catalogue domain is fetched as its own URL.

shortcut: one page per entry (``https://<domain>``); RSS items and sitemap URLs
come with worker#22, API records with their own adapters.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
"""

from meritum_core.checks.contracts import CatalogEntry


class EntryPageDiscovery:
    """DocumentDiscoveryPort that returns the entry's domain as one https URL.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """

    async def urls(self, entry: CatalogEntry) -> list[str]:  # ruff: ignore[no-self-use]  # the port is an instance method
        """Return the entry page (see ``DocumentDiscoveryPort.urls``).

        Args:
            entry: The catalogue entry; its domain may carry a path.

        Returns:
            ``["https://<domain>"]``.
        """
        return [f"https://{entry.domain}"]
