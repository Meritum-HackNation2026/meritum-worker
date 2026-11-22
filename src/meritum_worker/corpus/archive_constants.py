"""Constants of the page archiving: retention, rate limit and the stored terms.

Features:
    US-KOR-07, F-38
"""

from datetime import timedelta
from typing import Final

ARCHIVE_RETENTION: Final = timedelta(days=30)
"""How long a copy lives before the blob store's retention deletes it."""

ARCHIVE_RATE_LIMIT: Final = 5
"""Archiving requests one person may make per ``ARCHIVE_RATE_WINDOW``."""

ARCHIVE_RATE_WINDOW: Final = timedelta(hours=1)
"""The window the rate limit counts in."""

ARCHIVE_LEGAL_BASIS: Final = (
    "Prośba obywatela o archiwizację publicznej strony (art. 6 ust. 1 lit. a RODO);"
    " pobrano tylko treść dostępną bez logowania i opłaty, z poszanowaniem"
    " robots.txt i rezerwacji TDM."
)
"""Why we may keep a copy; stored with it."""

ARCHIVE_ACCESS_RULE: Final = "Widzi ją zlecający i moderatorzy; nie trafia do korpusu."
"""Who may see a copy; stored with it."""

ARCHIVE_DELETION_PROCEDURE: Final = (
    "Usunięcie na wniosek zlecającego albo właściciela treści; po terminie"
    " retencji kopię usuwa magazyn."
)
"""How a copy is removed; stored with it."""

ARCHIVE_CONTENT_TYPE: Final = "text/plain; charset=utf-8"
"""Media type of the stored text."""

MESSAGE_PAYWALL: Final = (
    "Ta strona wymaga logowania albo opłaty, więc nie powstała jej kopia."
    " Wklej tekst, który chcesz sprawdzić."
)
"""Told to the citizen when the page sits behind a login or paywall."""

MESSAGE_ROBOTS: Final = (
    "Właściciel strony nie zezwala na jej pobieranie, więc nie powstała kopia."
)
"""Told to the citizen when robots.txt or the TDM reservation forbids fetching."""

MESSAGE_FETCH_FAILED: Final = "Nie udało się pobrać strony, więc nie powstała kopia."
"""Told to the citizen when the page could not be fetched."""

MESSAGE_RATE_LIMIT: Final = "Wykorzystano limit próśb o archiwizację. Spróbuj później."
"""Told to the citizen over the rate limit."""

INSERT_ARCHIVE_SQL: Final = """
INSERT INTO page_archives (archive_id, blob_id, url, owner_id, sha256, archived_at,
    expires_at, legal_basis, access_rule, deletion_procedure)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (archive_id) DO NOTHING
"""
"""Stores one copy (core migration 0008); a retried step does not duplicate it."""

SELECT_ARCHIVE_SQL: Final = """
SELECT archive_id, blob_id, url, owner_id, sha256, archived_at, expires_at,
    legal_basis, access_rule, deletion_procedure
FROM page_archives WHERE archive_id = %s
"""
"""Reads one copy."""

DELETE_ARCHIVE_SQL: Final = "DELETE FROM page_archives WHERE archive_id = %s"
"""Forgets one copy."""

COUNT_ARCHIVES_SQL: Final = (
    "SELECT count(*) FROM page_archives WHERE owner_id = %s AND archived_at >= %s"
)
"""Counts one person's copies in the rate-limit window."""
