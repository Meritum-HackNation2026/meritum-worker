"""Constants of reading an image: messages, notes and limits.

Features:
    US-SPR-08, F-33
"""

from typing import Final

from meritum_worker.checks.constants import MAX_TRANSCRIPT_CHARS

READ_IMAGE_STEP: Final = "read_image"
"""Step name of reading an image with OCR; skipped without an image."""

MAX_IMAGE_TEXT_CHARS: Final = MAX_TRANSCRIPT_CHARS
"""Longest OCR text checked: the limit of a pasted text."""

UNSUPPORTED_IMAGE_MESSAGE: Final = (
    "The image is not supported; send a PNG, JPEG or WebP under 10 MiB, "
    "or paste the text."
)
"""Diagnostic for an image the OCR port does not accept."""

NO_TEXT_ON_IMAGE_MESSAGE: Final = "OCR found no text on the image."
"""Diagnostic for an image with no readable text."""

IMAGE_DATE_NOTE: Final = (
    "Data widoczna na obrazie sama nie potwierdza, kiedy treść naprawdę opublikowano."
)
"""Limitation of a claim dated from the image's text (F-33)."""

IMAGE_SEARCH_NOT_RUN_NOTE: Final = (
    "Nie szukaliśmy wcześniejszych wystąpień tego obrazu: żadna wyszukiwarka "
    "obrazów ani lokalna baza nie jest podłączona."
)
"""Limitation when no earlier-occurrence search ran (scenario F)."""

IMAGE_SEARCHED_NOTE: Final = (
    "Szukaliśmy wcześniejszych wystąpień obrazu w podłączonym źródle; "
    "znaleziono: {found}."
)
"""Limitation when the earlier-occurrence search ran; {found} is a count."""
