"""Constants of reading a video or post link from its public preview data.

Features:
    US-SPR-07, F-06, ADR-12
"""

import re
from typing import Final

PREVIEW_DOMAINS: Final = (
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "facebook.com",
    "fb.watch",
    "instagram.com",
)
"""Video and social services: their pages hold an application, not an article,
so only the Open Graph preview they publish is read."""

OG_TITLE: Final = "og:title"
"""Open Graph property of a page's title: the video's title or the post's author."""

OG_DESCRIPTION: Final = "og:description"
"""Open Graph property of a page's description: the post, or a cut video description."""

FULL_DESCRIPTION: Final = re.compile(r'"shortDescription":("(?:[^"\\]|\\.)*")')
"""The whole description of a YouTube video, a JSON string in the page's data."""

LOGIN_FORM: Final = re.compile(r"<input[^>]+type\s*=\s*[\"']?password", re.IGNORECASE)
"""A password field: the service answered with its login page, not the post."""

HTML_MEDIA_TYPE: Final = "text/html"
"""Media type of the pages whose preview is read."""

PREVIEW_MEDIA_TYPE: Final = "text/plain; charset=utf-8"
"""What a preview is labelled for core's fetcher, which reads plain text as is."""

PREVIEW_MAX_BYTES: Final = 5 * 1024 * 1024
"""Largest page read for its preview: core's limit of one response."""

PAGE_TOO_LARGE_STATUS: Final = 413
"""Status the preview transport answers for a page over ``PREVIEW_MAX_BYTES``."""

PREVIEW_ONLY_NOTE: Final = (
    "Z linku do serwisu {host} odczytaliśmy tylko tytuł i opis, które serwis"
    " udostępnia publicznie. Nie oglądaliśmy nagrania i nie czytaliśmy napisów"
    " ani komentarzy."
)
"""Limitation of a check that read a video or post link from its preview data."""
