"""Constants of matching a long live page's passages to the checked facts.

Features:
    US-KOR-04, US-SPR-04, F-13
"""

import re
from typing import Final

PASSAGE_TERM_MIN_CHARS: Final = 4
"""Shortest word that counts when passages are matched to the facts; shorter ones
are mostly conjunctions and prepositions. Numbers always count."""

PASSAGE_TERM_STEM_CHARS: Final = 5
"""Letters of a word compared when matching passages, so Polish inflections meet."""

PASSAGE_WORD: Final = re.compile(r"\w+")
"""A word or a number of a page or a fact, as matched against each other."""
