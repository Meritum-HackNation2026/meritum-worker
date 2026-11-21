"""Limits of the golden set case file.

Features:
    US-OBS-04, F-27, ADR-27
"""

from typing import Final

MAX_QUOTE_CHARS: Final = 300
"""Longest cited fragment of a source; full texts stay out of the repo (ADR-27)."""

MAX_TEXT_CHARS: Final = 4000
"""Longest case input text, the same limit as CheckRequest.text in meritum-core."""

REPEAT_VARIANTS: Final = frozenset({"same_session", "other_channel"})
"""Variants that repeat another case and so name it in related_case (G, H)."""
