"""build_euvsdisinfo_copy picks the copy the corpus settings name."""

import asyncio

from meritum_core.corpus import CorpusProvider, CorpusSettings

from meritum_worker import corpus
from meritum_worker.corpus.adapters import MemoryEuvsCopy, PostgresEuvsCopy

URL = "postgresql://meritum@localhost/meritum"


def test_postgres_settings_build_the_postgres_copy_without_connecting() -> None:
    settings = CorpusSettings(provider=CorpusProvider.POSTGRES, database_url=URL)
    assert isinstance(corpus.build_euvsdisinfo_copy(settings), PostgresEuvsCopy)


def test_memory_settings_build_an_empty_memory_copy() -> None:
    copy = corpus.build_euvsdisinfo_copy(CorpusSettings(provider=CorpusProvider.MEMORY))
    assert isinstance(copy, MemoryEuvsCopy)
    assert asyncio.run(copy.entries()) == []


def test_no_settings_build_the_memory_copy() -> None:
    assert isinstance(corpus.build_euvsdisinfo_copy(), MemoryEuvsCopy)
