"""European Commission Press Corner documents read from its JSON API.

The ``detail`` pages of Press Corner render in the browser, so their HTML has no
text. The same document comes from the page's own JSON API; the corpus keeps the
``detail`` link, which a person can open.

Features:
    US-KOR-02, US-KOR-03, F-10, F-13, ADR-32
"""

import html
import re
from datetime import datetime

from meritum_core.corpus.fetching import FetchedPage
from pydantic import BaseModel, Field

from meritum_worker.corpus.catalog_api.constants import HTML_TAG
from meritum_worker.corpus.ingest_constants import PRESSCORNER_API, PRESSCORNER_DETAIL


class _Content(BaseModel):
    title: str = Field(min_length=1)
    html_content: str = Field(alias="htmlContent")


class _Document(BaseModel):
    content: _Content = Field(alias="docuLanguageResource")
    published: datetime | None = Field(default=None, alias="publishDate")


def presscorner_api_url(url: str) -> str | None:
    """The JSON API address of a Press Corner document page.

    Args:
        url: Any page URL.

    Returns:
        The API request for a ``detail`` page; None for any other URL.

    Features:
        US-KOR-02, US-KOR-03, F-10, F-13
    """
    found = re.match(PRESSCORNER_DETAIL, url)
    if found is None:
        return None
    reference = found["reference"].upper().replace("_", "/")
    return PRESSCORNER_API.format(reference=reference, language=found["language"])


def presscorner_page(url: str, answer: str) -> FetchedPage:
    """The document of one API answer as a page under its ``detail`` link.

    Only the title and the body are kept; contacts and quotes' authors are not.

    Args:
        url: The ``detail`` page.
        answer: The raw, untrusted JSON answer.

    Returns:
        The page: title, then the body without HTML tags, dated by publication.

    Raises:
        ValueError: The answer is not a Press Corner document.

    Features:
        US-KOR-02, US-KOR-03, F-10, F-13
    """  # ruff: ignore[docstring-extraneous-exception]  # pydantic's ValidationError
    document = _Document.model_validate_json(answer)
    body = " ".join(
        html.unescape(re.sub(HTML_TAG, " ", document.content.html_content)).split()
    )
    return FetchedPage(
        url=url,
        content_type="text/html",
        untrusted_text=f"{document.content.title.strip()}\n\n{body}",
        published_at=document.published.date() if document.published else None,
    )
