"""NATO's English news listing, the JSON its news page loads its articles from.

NATO's sitemap is past core's size limit and its small child sitemap lists only
French pages; the news page itself renders its list in the browser.

Features:
    US-KOR-03, F-13
"""

from datetime import date, datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

from pydantic import BaseModel, Field, ValidationError

from meritum_worker.corpus.documents import DiscoveredPage
from meritum_worker.corpus.errors import FeedUnreadableError
from meritum_worker.corpus.feeds.constants import (
    MAX_PAGES_PER_ENTRY,
    NATO_DATE_FORMAT,
    NATO_ORIGIN,
)


class _Article(BaseModel):
    link: str = Field(min_length=1)
    page_date: str = Field(default="", alias="pageDate")


class _Listing(BaseModel):
    pages: list[_Article]


def parse_nato_news(answer: str) -> tuple[DiscoveredPage, ...]:
    """The articles of one answer of NATO's news listing, in its order.

    Args:
        answer: The raw, untrusted JSON; the listing is asked newest first.

    Returns:
        Each article's address on www.nato.int without the query string, with
        its date, at most ``MAX_PAGES_PER_ENTRY``.

    Raises:
        FeedUnreadableError: The JSON is broken or is not a news listing.

    Features:
        US-KOR-03, F-13
    """
    try:
        listing = _Listing.model_validate_json(answer)
    except ValidationError as error:
        raise FeedUnreadableError from error
    if not listing.pages:
        raise FeedUnreadableError
    return tuple(
        DiscoveredPage(url=_address(a.link), published_on=_date(a.page_date))
        for a in listing.pages[:MAX_PAGES_PER_ENTRY]
    )


def _address(link: str) -> str:
    # The listing adds an empty ``?selectedLocale=`` to every link.
    parts = urlsplit(urljoin(NATO_ORIGIN, link))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _date(value: str) -> date | None:
    try:
        return datetime.strptime(value, NATO_DATE_FORMAT).date() if value else None  # ruff: ignore[call-datetime-strptime-without-zone]  # a calendar date, no time
    except ValueError:
        return None
