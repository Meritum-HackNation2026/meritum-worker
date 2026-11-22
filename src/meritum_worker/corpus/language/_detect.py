"""Language of a source text, so an English source is cited with ``language "en"``.

Features:
    US-KOR-06, F-35
"""

import re

from meritum_worker.corpus.language.constants import (
    ENGLISH_WORDS,
    POLISH_LETTERS,
    POLISH_WORDS,
    WORD_PATTERN,
)


def detect_language(text: str) -> str:
    """Tell English from Polish; the catalogue holds only these two.

    A Polish letter means Polish. Otherwise the more frequent of the common
    English and Polish function words wins, and a tie is Polish.

    Args:
        text: The source text.

    Returns:
        ``"en"`` or ``"pl"``.

    Features:
        US-KOR-06, F-35
    """
    if POLISH_LETTERS.intersection(text.lower()):
        return "pl"
    words = re.findall(WORD_PATTERN, text.lower())
    english = sum(w in ENGLISH_WORDS for w in words)
    polish = sum(w in POLISH_WORDS for w in words)
    return "en" if english > polish else "pl"
