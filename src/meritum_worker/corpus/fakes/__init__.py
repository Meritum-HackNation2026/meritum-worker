"""Fakes of the corpus slice for tests and behave scenarios, no network.

Features:
    US-KOR-08, US-KOR-02, US-KOR-04, US-KOR-05, F-10, F-11, F-12, F-13
"""

from meritum_worker.corpus.adapters import MemoryCorpusWriter

from ._catalog import FakeCatalogSite
from ._euvs import FakeEuvsDisinfoServer
from ._web_search import FakeWebSearch

__all__ = [
    "FakeCatalogSite",
    "FakeEuvsDisinfoServer",
    "FakeWebSearch",
    "MemoryCorpusWriter",
]
