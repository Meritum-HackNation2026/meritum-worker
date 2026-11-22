"""Adapters of the corpus_ready build, built only by ``corpus.ready.factory``.

Features:
    US-KOR-02, F-12
"""

from ._postgres import PostgresReadyStore

__all__ = ["PostgresReadyStore"]
