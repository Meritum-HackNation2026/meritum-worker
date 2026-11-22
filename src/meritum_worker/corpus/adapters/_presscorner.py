"""Page fetcher that reads Press Corner documents from their JSON API.

Features:
    US-KOR-02, US-KOR-03, F-10, F-13, ADR-32
"""

from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    PageFetcherPort,
    PageFetchError,
)

from meritum_worker.corpus.presscorner import presscorner_api_url, presscorner_page


class PresscornerFetcher:
    """PageFetcherPort reading Press Corner ``detail`` pages through their API.

    Both inner fetchers are core's, so the SSRF guard, robots.txt and
    Content-Signal apply to the API request as to any page.

    Args:
        pages: Core's page fetcher, for every other URL.
        api: Core's fetcher over ``JsonAsTextTransport``, for the API request.

    Features:
        US-KOR-02, US-KOR-03, F-10, F-13, ADR-32
    """

    def __init__(self, pages: PageFetcherPort, api: PageFetcherPort) -> None:
        self._pages = pages
        self._api = api

    async def fetch(self, url: str, *, purpose: FetchPurpose) -> FetchedPage:
        """Fetch one page (see ``PageFetcherPort.fetch``).

        Args:
            url: An absolute http(s) URL.
            purpose: Passed on to the inner fetcher.

        Returns:
            The page; a Press Corner document keeps its ``detail`` URL.

        Raises:
            PageFetchError: The fetch failed, or the API answered something
                other than a document (``unsupported_content``).
        """
        api_url = presscorner_api_url(url)
        if api_url is None:
            return await self._pages.fetch(url, purpose=purpose)
        answer = await self._api.fetch(api_url, purpose=purpose)
        try:
            return presscorner_page(url, answer.untrusted_text)
        except ValueError:
            raise PageFetchError(FetchFailureReason.UNSUPPORTED_CONTENT) from None
