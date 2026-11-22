"""The passages of a long live page that are closest to the checked facts.

Pages of gov.pl and ZUS open with menus and cookie banners, so their first
characters often miss the sentence that decides a claim. Within the same
budget we keep the passages sharing the most words and numbers with the
facts, in page order. Plain word overlap: no model and no reranker call.

Features:
    US-KOR-04, US-SPR-04, F-13
"""

from collections.abc import Sequence

from meritum_worker.corpus.chunking import chunk_text
from meritum_worker.corpus.constants import MAX_PAGE_TEXT_CHARS, PARAGRAPH_SEPARATOR
from meritum_worker.corpus.passage_constants import (
    PASSAGE_TERM_MIN_CHARS,
    PASSAGE_TERM_STEM_CHARS,
    PASSAGE_WORD,
)


def closest_passages(text: str, facts: Sequence[str]) -> str:
    """Keep the passages of ``text`` that best match ``facts``, in page order.

    A text within ``MAX_PAGE_TEXT_CHARS`` is returned as it is. A longer one
    is split by ``chunk_text``; passages are ranked by how many of the facts'
    terms they share (earlier first on a tie) and taken while they fit the
    budget, joined by a blank line. With no facts this is the page's opening.

    Args:
        text: The page text (untrusted data).
        facts: The checked facts or their search queries.

    Returns:
        At most ``MAX_PAGE_TEXT_CHARS`` characters, every passage verbatim.

    Features:
        US-KOR-04, US-SPR-04, F-13
    """
    if len(text) <= MAX_PAGE_TEXT_CHARS:
        return text
    wanted = {term for fact in facts for term in _terms(fact)}
    passages = chunk_text(text)
    ranked = sorted(
        range(len(passages)),
        key=lambda i: (-len(wanted & set(_terms(passages[i]))), i),
    )
    kept: list[int] = []
    used = 0
    for i in ranked:
        cost = len(passages[i]) + (len(PARAGRAPH_SEPARATOR) if kept else 0)
        if used + cost <= MAX_PAGE_TEXT_CHARS:
            kept.append(i)
            used += cost
    return PARAGRAPH_SEPARATOR.join(passages[i] for i in sorted(kept))


def _terms(text: str) -> list[str]:
    # A short stem lets Polish inflections meet: "minimalna" and "minimalne".
    return [
        word if word.isdigit() else word[:PASSAGE_TERM_STEM_CHARS]
        for word in PASSAGE_WORD.findall(text.casefold())
        if word.isdigit() or len(word) >= PASSAGE_TERM_MIN_CHARS
    ]
