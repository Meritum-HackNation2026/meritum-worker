"""A fake set of catalogue sites for tests and behave scenarios, no network.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12
"""

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    PageFetchError,
)


class FakeCatalogSite:
    """Discovery and fetcher in one: every domain has numbered pages.

    Args:
        pages_per_domain: Pages each entry's discovery returns.

    Attributes:
        discovered: ``(domain, urls)`` of every discovery call, in order.
        fetched: Every fetched URL with its purpose, in order.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12
    """

    def __init__(self, pages_per_domain: int) -> None:
        self._pages = pages_per_domain
        self._reserved: set[str] = set()
        self._failing: dict[str, FetchFailureReason] = {}
        self._texts: dict[str, str] = {}
        self.discovered: list[tuple[str, list[str]]] = []
        self.fetched: list[tuple[str, FetchPurpose]] = []

    def reserve_mining(self, domain: str) -> None:
        """Mark every page of a domain with TDM meta tags.

        Args:
            domain: The domain.
        """
        self._reserved.add(domain)

    def fail(self, url: str, reason: FetchFailureReason) -> None:
        """Make one page fail like the core fetcher does.

        Args:
            url: The page.
            reason: The failure.
        """
        self._failing[url] = reason

    def set_text(self, url: str, text: str) -> None:
        """Change what one page says.

        Args:
            url: The page.
            text: Its new main text.
        """
        self._texts[url] = text

    async def urls(self, entry: CatalogEntry) -> list[str]:
        """Return the domain's pages (see ``DocumentDiscoveryPort.urls``).

        Args:
            entry: The catalogue entry.

        Returns:
            ``https://<domain>/strona-<i>`` for each page.
        """
        urls = [f"https://{entry.domain}/strona-{i}" for i in range(self._pages)]
        self.discovered.append((entry.domain, urls))
        return urls

    async def fetch(self, url: str, *, purpose: FetchPurpose) -> FetchedPage:
        """Return the page's text (see ``PageFetcherPort.fetch``).

        Args:
            url: The page.
            purpose: Why it is fetched.

        Returns:
            The page.

        Raises:
            PageFetchError: The page was set to fail.
        """
        self.fetched.append((url, purpose))
        if url in self._failing:
            raise PageFetchError(self._failing[url])
        domain = url.split("/")[2]
        default = f"Komunikat ze strony {url}.\n\nTreść urzędowa dla obywateli."
        return FetchedPage(
            url=url,
            content_type="text/html",
            untrusted_text=self._texts.get(url, default),
            tdm_reserved=domain in self._reserved,
        )
