"""Pure rules of claim similarity: embeddings close, numbers, months and names equal.

Features:
    US-MOD-02, F-24
"""

import math
import re
from collections.abc import Sequence

from meritum_worker.moderation.constants import (
    MONTH_STEMS,
    NAME_STEM_CHARS,
    NUMBER_PATTERN,
    PROPER_NAME_PATTERN,
)


def _numbers(text: str) -> frozenset[str]:
    return frozenset(re.sub(r"\D", "", n) for n in NUMBER_PATTERN.findall(text))


def _months(text: str) -> frozenset[str]:
    words = re.findall(r"[^\W\d]+", text.casefold())
    return frozenset(s for s in MONTH_STEMS if any(w.startswith(s) for w in words))


def _names(text: str) -> frozenset[str]:
    return frozenset(
        m.casefold()[:NAME_STEM_CHARS] for m in PROPER_NAME_PATTERN.findall(text)
    )


def facts_agree(first: str, second: str) -> bool:
    """Whether two claims state the same numbers, months and proper names.

    Different numbers or months are different claims whatever the wording;
    proper names must overlap when both claims have some.

    Args:
        first: one claim.
        second: the other claim.

    Returns:
        True when nothing contradicts the claims being the same.

    Features:
        US-MOD-02, F-24
    """
    if _numbers(first) != _numbers(second) or _months(first) != _months(second):
        return False
    names = _names(first), _names(second)
    return not all(names) or bool(names[0] & names[1])


def cosine(first: Sequence[float], second: Sequence[float]) -> float:
    """Cosine similarity of two vectors; 0 when one is all zeros.

    Args:
        first: one vector.
        second: the other vector.

    Returns:
        The similarity, from -1 to 1.

    Features:
        US-MOD-02, F-24
    """
    norms = math.hypot(*first) * math.hypot(*second)
    dot = sum(a * b for a, b in zip(first, second, strict=True))
    return dot / norms if norms else 0.0
