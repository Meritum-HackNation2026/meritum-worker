"""Discovery by entry page: a static catalogue domain is fetched as its own URL.

Features:
    US-KOR-02, US-KOR-03, US-KOR-05, F-10, F-12, F-13, ADR-32
"""

from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.corpus.documents import DiscoveredPage


class EntryPageDiscovery:
    """DocumentDiscoveryPort that returns the entry's domain as one https page.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """

    async def pages(self, entry: CatalogEntry) -> list[DiscoveredPage]:  # ruff: ignore[no-self-use]  # the port is an instance method
        """Return the entry page (see ``DocumentDiscoveryPort.pages``).

        Args:
            entry: The catalogue entry; its domain may carry a path.

        Returns:
            ``https://<domain>``, without a date.
        """
        return [DiscoveredPage(url=f"https://{entry.domain}")]
