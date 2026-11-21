"""Screen long texts in overlapping chunks that fit a provider's request limit.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-35
"""

from collections.abc import Awaitable, Callable

from meritum_core.security.injection import TextRange

from meritum_worker.security.adapters._http import skipped
from meritum_worker.security.constants import (
    CHUNK_CHARS,
    CHUNK_OVERLAP_CHARS,
    MAX_CHUNKS,
)
from meritum_worker.security.settings import InjectionGateProvider


def _chunks(text: str) -> list[TextRange]:
    ranges: list[TextRange] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            # Cut at the last space so no word is split; hard cut in a long word.
            space = text.rfind(" ", start + CHUNK_OVERLAP_CHARS + 1, end)
            end = space + 1 if space >= 0 else end
        ranges.append(TextRange(start, end))
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP_CHARS
    return ranges


async def screen_chunks(
    text: str,
    flags: Callable[[str], Awaitable[bool | None]],
    provider: InjectionGateProvider,
) -> tuple[TextRange, ...]:
    """Ask ``flags`` about each chunk of ``text`` and return the flagged chunks.

    Chunks overlap by ``CHUNK_OVERLAP_CHARS``, so an instruction shorter than
    that across a cut still lands whole in one chunk. Blank chunks are not sent.
    The first skipped chunk stops the rest: the gate is already skipped, and a
    provider outage must not cost one timeout per chunk. Only ``MAX_CHUNKS``
    chunks are screened; the rest of a longer text is skipped with a log line.

    Args:
        text: User or page text.
        flags: Screens one chunk: True when flagged, False when clean, None when
            the gate was skipped (already logged).
        provider: Provider name for the skip log.

    Returns:
        The range of every flagged chunk, in order.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-35
    """
    ranges = _chunks(text)
    if len(ranges) > MAX_CHUNKS:
        skipped(provider, f"rest of the text skipped after {MAX_CHUNKS} chunks")
    found: list[TextRange] = []
    for chunk in ranges[:MAX_CHUNKS]:
        part = text[chunk.start : chunk.end]
        verdict = await flags(part) if part.strip() else False
        if verdict is None:
            break
        if verdict:
            found.append(chunk)
    return tuple(found)
