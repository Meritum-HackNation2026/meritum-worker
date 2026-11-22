"""Words and letters that tell English from Polish.

Features:
    US-KOR-06, F-35
"""

from typing import Final

WORD_PATTERN: Final = r"[^\W\d_]+"
"""A run of letters; digits and underscores split words."""

POLISH_LETTERS: Final = frozenset("ąćęłńóśźż")
"""Letters English lacks; one of them marks a text as Polish."""

ENGLISH_WORDS: Final = frozenset(
    [
        "the",
        "of",
        "and",
        "to",
        "in",
        "is",
        "on",
        "that",
        "for",
        "with",
        "by",
        "from",
        "as",
        "are",
        "was",
        "were",
        "be",
        "this",
    ]
)
"""Common English function words; they tell English from unaccented Polish."""

POLISH_WORDS: Final = frozenset(
    [
        "i",
        "w",
        "na",
        "z",
        "do",
        "się",
        "że",
        "o",
        "jest",
        "nie",
        "przez",
        "dla",
        "po",
        "oraz",
        "od",
        "to",
        "jak",
        "ustawy",
    ]
)
"""Common Polish function words, written without accents."""
