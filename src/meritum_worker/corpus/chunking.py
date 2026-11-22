"""Splitting a fetched document into short passages for search and quoting.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12
"""

from meritum_worker.corpus.constants import CHUNK_MAX_CHARS, PARAGRAPH_SEPARATOR


def chunk_text(text: str) -> list[str]:
    """Split a document into passages of at most ``CHUNK_MAX_CHARS`` characters.

    Paragraphs (separated by a blank line) are grouped while they fit; a longer
    paragraph is split between words, and a single longer word is cut. Users see
    only these passages with a link, never the whole text (US-KOR-05).

    Args:
        text: The document's main text (untrusted data).

    Returns:
        The passages in document order; empty for blank text.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12
    """
    paragraphs = [
        p.strip() for p in text.replace("\r\n", "\n").split(PARAGRAPH_SEPARATOR)
    ]
    pieces = [piece for p in paragraphs if p for piece in _split_long(p)]
    chunks: list[str] = []
    for piece in pieces:
        joined = f"{chunks[-1]}{PARAGRAPH_SEPARATOR}{piece}" if chunks else piece
        if chunks and len(joined) <= CHUNK_MAX_CHARS:
            chunks[-1] = joined
        else:
            chunks.append(piece)
    return chunks


def _split_long(paragraph: str) -> list[str]:
    if len(paragraph) <= CHUNK_MAX_CHARS:
        return [paragraph]
    parts: list[str] = []
    current = ""
    for word in paragraph.split():
        for cut in _cut(word):
            candidate = f"{current} {cut}" if current else cut
            if len(candidate) <= CHUNK_MAX_CHARS:
                current = candidate
            else:
                parts.append(current)
                current = cut
    return [*parts, current] if current else parts


def _cut(word: str) -> list[str]:
    return [word[i : i + CHUNK_MAX_CHARS] for i in range(0, len(word), CHUNK_MAX_CHARS)]
