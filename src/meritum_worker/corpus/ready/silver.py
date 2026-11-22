"""Silver: the bronze text cleaned deterministically, as spans of the bronze text.

No LLM touches the text. Cleaning only drops whole paragraphs (menus, footers,
repeated furniture), so every kept span is still ``full_text[start:end]``.

Features:
    US-KOR-02, F-12
"""

import re

from meritum_worker.corpus.constants import PARAGRAPH_SEPARATOR
from meritum_worker.corpus.ready.constants import (
    BOILERPLATE_PATTERNS,
    MENU_LINE_CHARS,
    MENU_MIN_LINES,
)
from meritum_worker.corpus.ready.models import Span


def paragraphs(full_text: str) -> list[Span]:
    """Split the bronze text into paragraphs, blank ones dropped, spaces trimmed.

    Args:
        full_text: The bronze document text.

    Returns:
        One span per paragraph, in order.

    Features:
        US-KOR-02, F-12
    """
    spans: list[Span] = []
    start = 0
    for part in full_text.split(PARAGRAPH_SEPARATOR):
        stripped = part.strip()
        if stripped:
            begin = start + part.index(stripped)
            spans.append(Span(start=begin, end=begin + len(stripped)))
        start += len(part) + len(PARAGRAPH_SEPARATOR)
    return spans


def clean(full_text: str) -> list[Span]:
    """The paragraphs of the bronze text without site furniture.

    A paragraph is dropped when every line is furniture: a known boilerplate
    line, or one of at least ``MENU_MIN_LINES`` short lines with no full stop
    (a menu). A paragraph seen before in the same document is dropped too.

    Args:
        full_text: The bronze document text.

    Returns:
        The kept spans, in order.

    Features:
        US-KOR-02, F-12
    """
    seen: set[str] = set()
    kept: list[Span] = []
    for span in paragraphs(full_text):
        text = full_text[span.start : span.end]
        if text not in seen and not _is_furniture(text):
            kept.append(span)
        seen.add(text)
    return kept


def silver_text(full_text: str, spans: list[Span]) -> str:
    """The cleaned text stored in ``corpus_ready.silver_documents``.

    Args:
        full_text: The bronze document text.
        spans: Its kept spans.

    Returns:
        The kept paragraphs joined like bronze paragraphs.

    Features:
        US-KOR-02, F-12
    """
    return PARAGRAPH_SEPARATOR.join(full_text[s.start : s.end] for s in spans)


def _is_furniture(paragraph: str) -> bool:
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if all(_is_boilerplate(line) for line in lines):
        return True
    short = [line for line in lines if len(line) < MENU_LINE_CHARS and "." not in line]
    return len(lines) >= MENU_MIN_LINES and len(short) == len(lines)


def _is_boilerplate(line: str) -> bool:
    return any(re.search(pattern, line) for pattern in BOILERPLATE_PATTERNS)
