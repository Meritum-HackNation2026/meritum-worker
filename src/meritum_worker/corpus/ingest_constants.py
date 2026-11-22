"""Constants of the catalogue ingestion that ``constants.py`` has no room for.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
"""

from typing import Final

INJECTION_UNAVAILABLE: Final = "injection_unavailable"
"""Failure reason of a page the injection detector could not scan (its provider
failed); the page is not stored unscanned and the next one follows."""
