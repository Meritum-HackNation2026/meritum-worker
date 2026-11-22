"""The major media the last-resort search may cite.

Features:
    US-KOR-04, F-13, ADR-07
"""

from typing import Final

NEWS_MEDIA: Final[tuple[tuple[str, str, str], ...]] = (
    ("bbc.com", "BBC", "bbc"),
    ("reuters.com", "Reuters", "reuters"),
    ("apnews.com", "Associated Press", "ap"),
    ("cnbc.com", "CNBC", "cnbc"),
    ("nytimes.com", "The New York Times", "nyt"),
    ("theguardian.com", "The Guardian", "the-guardian"),
    ("ft.com", "Financial Times", "ft"),
    ("politico.eu", "Politico Europe", "politico-europe"),
    ("ansa.it", "ANSA", "ansa"),
    ("tg24.sky.it", "Sky TG24", "sky-tg24"),
    ("pap.pl", "Polska Agencja Prasowa", "pap"),
    ("onet.pl", "Onet", "onet"),
    ("wp.pl", "Wirtualna Polska", "wirtualna-polska"),
    ("interia.pl", "Interia", "interia"),
    ("gazeta.pl", "Gazeta.pl", "gazeta-pl"),
    ("rmf24.pl", "RMF24", "rmf24"),
    ("tvn24.pl", "TVN24", "tvn24"),
    ("polsatnews.pl", "Polsat News", "polsat-news"),
    ("rp.pl", "Rzeczpospolita", "rzeczpospolita"),
    ("polityka.pl", "Polityka", "polityka"),
    ("notesfrompoland.com", "Notes from Poland", "notes-from-poland"),
)
"""Domain, publisher and publisher id of each outlet, international first."""

NEWS_LICENSE: Final = "prawo autorskie wydawcy; krótki fragment z linkiem"
"""The licence note of every outlet: a short quote with the link, nothing more."""

NEWS_QUALIFIED_BECAUSE: Final = (
    "Duża redakcja informacyjna; źródło wtórne, pytane dopiero gdy katalog nic nie dał."
)
"""Why the outlets qualify, as the catalogue entry says it."""
