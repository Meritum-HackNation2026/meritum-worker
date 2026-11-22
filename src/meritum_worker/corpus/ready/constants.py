"""Settings of the corpus_ready build (not secrets): schedule, chunk sizes, cleaning.

Features:
    US-KOR-02, US-ZRD-05, F-12
"""

from typing import Final

BUILD_WORKFLOW: Final = "corpus_ready_build"
"""DBOS name of the gold build workflow and of its schedule."""

BUILD_STEP: Final = "corpus_ready_build"
"""Name of the one step that migrates corpus_ready and builds silver and gold."""

BUILD_SCHEDULE: Final = "40 * * * *"
"""Hourly, twenty minutes before the next snapshot (``0 * * * *``), so a new
snapshot sees the gold built from the documents ingested before it."""

MAX_CHUNK_CHARS: Final = 1200
"""Longest gold chunk; a longer article is split by ``ust.``, a page by paragraph."""

EXCERPT_CHARS: Final = 300
"""Media and fact-checker documents get one excerpt of at most this many characters."""

MENU_LINE_CHARS: Final = 40
"""A line shorter than this, with no full stop, looks like a menu or footer item."""

MENU_MIN_LINES: Final = 3
"""A paragraph of at least this many short lines is navigation, not content."""

HEADING_MAX_CHARS: Final = 120
"""A one-line paragraph up to this long without a full stop is a heading."""

EMBED_BATCH: Final = 64
"""Chunk texts embedded per call."""

LEGAL_ACT_KIND: Final = "akt_prawny"
"""Catalogue ``kind`` of legal-act sources (api.sejm.gov.pl ELI)."""

FULL_TEXT_KINDS: Final = frozenset({"akt_prawny", "instytucja", "dane_publiczne"})
"""Catalogue kinds whose full text goes to gold; others get an excerpt only."""

CONSOLIDATED_TYPE: Final = "Obwieszczenie"
"""ELI ``type`` of an announcement of a consolidated text (tekst jednolity)."""

BOILERPLATE_PATTERNS: Final = (
    r"(?i)^©?\s*Kancelaria Sejmu\s+s\.\s*\d+/\d+$",
    r"(?i)(pliki cookies|polityka prywatności|przejdź do treści|udostępnij)",
    r"(?i)^(menu|szukaj|wyszukaj|zamknij|drukuj|powrót)$",
)
"""Lines that are site furniture, never content (research-ingest A1, A3)."""

NUMBER_PATTERN: Final = (
    r"(?P<value>\d[\d\s]*(?:[.,]\d+)?)\s?"
    r"(?P<unit>zł|złotych|%|proc\.|mln|mld|tys\.|EUR|euro)"
)
"""A number with its unit; the period is the nearest year in the same sentence."""

YEAR_PATTERN: Final = r"\b(19|20)\d{2}\b"
"""A year that gives a number its period."""

ACT_META_LINE: Final = (
    r"^(?P<type>[^,]+), ELI: (?P<eli>\S+), (?P<address>.+?), "
    r"status: (?P<status>[^,]+?)"
    r"(?:, w mocy od (?P<since>\d{4}-\d{2}-\d{2}))?"
    r"(?: do (?P<until>\d{4}-\d{2}-\d{2}))?"
    r", ogłoszono (?P<published>\d{4}-\d{2}-\d{2})\.$"
)
"""The metadata line ``catalog_api.acts._header`` writes under an act's title;
read only until core's ``corpus.document_legal_meta`` has the act (core#167)."""

SUBSECTION_START: Final = r"(?m)^\d+[a-z]*\.\s"
"""A line opening a numbered ``ust.`` inside an article."""

CHAPTER_LABELS: Final = ("Rozdział", "DZIAŁ")
"""Unit labels (``act_units``) that open a chapter; their text is chunk context."""

SENTENCE_END: Final = r"(?<=[.;!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])"
"""A sentence boundary: punctuation, then a capital letter, so ``2026 r. wyniesie``
stays one sentence."""

CANARY_QUERIES: Final = (
    ("Warszawa jest stolicą Polski", "Stolicą Rzeczypospolitej Polskiej jest Warszawa"),
    ("Sejm składa się z 460 posłów", "460 posłów"),
    ("płaca minimalna w 2026 roku wynosi 4806 zł", "4806"),
    ("podstawowa stawka VAT wynosi 23 procent", "23 %"),
    ("najniższa stawka PIT to 12 procent", "12 %"),
)
"""Canary claims and a phrase the right chunk contains (research-ingest §0.7);
``scripts/corpus_ready_canary.py`` reports hit@5 for bronze and gold."""

CANARY_TOP_K: Final = 5
"""Passages a canary query may look at for its hit."""
