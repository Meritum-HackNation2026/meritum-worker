"""Local canary report: hit@5 of today's corpus search against gold (corpus_ready).

Run by hand against a database with a snapshot and a gold build, never in CI:
``MERITUM_CORPUS_PROVIDER=postgres MERITUM_CORPUS_DATABASE_URL=... uv run python
scripts/corpus_ready_canary.py <corpus_version>``. The embeddings settings must be
the ones the corpus was indexed with. Prints a Markdown table.

Features:
    US-KOR-02, US-ZRD-05, F-12
"""

import asyncio
import os
import sys
from datetime import UTC, datetime

from meritum_core.corpus import CorpusSettings, build_corpus_search
from meritum_core.corpus.ready.constants import READY_FLAG_ENV
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker.corpus.ready.constants import CANARY_QUERIES, CANARY_TOP_K


async def hits(version: str, *, gold: bool) -> list[bool]:
    """Whether each canary finds its phrase in the top passages.

    Args:
        version: The pinned snapshot.
        gold: Search with ``MERITUM_CORPUS_READY`` on.

    Returns:
        One hit flag per canary query.

    Features:
        US-KOR-02, US-ZRD-05, F-12
    """
    os.environ[READY_FLAG_ENV] = "true" if gold else "false"
    search = build_corpus_search(
        CorpusSettings(), build_embeddings(EmbeddingsSettings())
    )
    today = datetime.now(UTC).date()
    found = [
        await search.search(
            q, claim_date=today, corpus_version=version, limit=CANARY_TOP_K
        )
        for q, _ in CANARY_QUERIES
    ]
    return [
        any(phrase in p.text for p in passages)
        for (_, phrase), passages in zip(CANARY_QUERIES, found, strict=True)
    ]


def main() -> None:
    """Print the canary table for the snapshot named on the command line.

    Features:
        US-KOR-02, US-ZRD-05, F-12
    """
    version = sys.argv[1]
    bronze = asyncio.run(hits(version, gold=False))
    gold = asyncio.run(hits(version, gold=True))
    lines = ["| zapytanie | bronze | gold |", "|---|---|---|"]
    lines += [
        f"| {q} | {'tak' if b else 'nie'} | {'tak' if g else 'nie'} |"
        for (q, _), b, g in zip(CANARY_QUERIES, bronze, gold, strict=True)
    ]
    n = len(CANARY_QUERIES)
    lines.append(f"| hit@{CANARY_TOP_K} | {sum(bronze)}/{n} | {sum(gold)}/{n} |")
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
