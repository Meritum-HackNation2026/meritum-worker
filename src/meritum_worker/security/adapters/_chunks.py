"""Screen long texts in overlapping chunks that fit a provider's request limit.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-35
"""

from collections.abc import Awaitable, Callable

from meritum_core.security.injection import TextRange

from meritum_worker.security.constants import CHUNK_CHARS, CHUNK_OVERLAP_CHARS


def _chunks(text: str) -> list[TextRange]:
    ranges: list[TextRange] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            # Cut at the last space so no word is split; hard cut in a long word.
            end = text.rfind(" ", start + CHUNK_OVERLAP_CHARS + 1, end) + 1 or end
        ranges.append(TextRange(start, end))
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP_CHARS
    return ranges


async def screen_chunks(
    text: str, flags: Callable[[str], Awaitable[bool]]
) -> tuple[TextRange, ...]:
    """Ask ``flags`` about each chunk of ``text`` and return the flagged chunks.

    Chunks overlap by ``CHUNK_OVERLAP_CHARS``, so an instruction shorter than
    that across a cut still lands whole in one chunk. Blank chunks are not sent.

    Args:
        text: User or page text.
        flags: Screens one chunk; True when the provider flags it.

    Returns:
        The range of every flagged chunk, in order.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-35
    """
    return tuple(
        [
            found
            for found in _chunks(text)
            if text[found.start : found.end].strip()
            and await flags(text[found.start : found.end])
        ]
    )
