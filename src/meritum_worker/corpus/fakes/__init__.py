"""Fakes of the corpus slice for tests and behave scenarios, no network.

Features:
    US-KOR-08, US-KOR-02, US-KOR-03, US-KOR-04, US-KOR-05, US-KOR-07, F-10, F-11, F-12,
    F-13, F-38
"""

from meritum_worker.corpus.adapters import MemoryArchiveRegistry, MemoryCorpusWriter

from ._api import FakePublicApi
from ._catalog import FakeCatalogSite
from ._euvs import FakeEuvsDisinfoServer
from ._fact_check import FakeFactCheck
from ._feeds import FakeFeedServer
from ._web_search import FakeWebSearch

__all__ = [
    "FakeCatalogSite",
    "FakeEuvsDisinfoServer",
    "FakeFactCheck",
    "FakeFeedServer",
    "FakePublicApi",
    "FakeWebSearch",
    "MemoryArchiveRegistry",
    "MemoryCorpusWriter",
]
