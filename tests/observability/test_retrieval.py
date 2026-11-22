"""Embeddings retrieval in a corpus snapshot, hand-made vectors (#40, #113)."""

import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from meritum_core.corpus import Passage
from meritum_core.shared.embeddings import Vector

from meritum_worker.observability import (
    GoldenCase,
    GoldenSet,
    SnapshotCorpus,
    compare_embeddings,
    load_embeddings_config,
    load_snapshot_file,
    meritum_eval,
    score_retrieval,
)
from meritum_worker.observability.snapshot import MeteredEmbeddings

type Make[T] = Callable[..., T]

AT = datetime(2026, 11, 22, tzinfo=UTC)
VERSION = "2026-11-22T04:00Z"
CONFIG = """
name = "{name}"
usd_per_million_chars = 2.0

[embeddings]
provider = "stub"
"""

# Passage texts share no word with the queries, so only the vectors rank them.
VECTORS: dict[str, Vector] = {
    "Strefa A": (1.0, 0.0),
    "Strefa B": (1.0, 0.1),  # nearer a than b: b ranks second
    "Strefa C": (0.0, 1.0),
    "pierwszy": (2.0, 0.0),  # not unit length: the search compares directions
    "drugi": (0.0, 1.0),
    "obcy": (0.6, 0.8),
}


def _source(slug: str) -> dict[str, str]:
    return {
        "url": f"https://www.gov.pl/{slug}",
        "publisher": "Gmina Pcim",
        "title": f"Tytuł {slug}",
        "quote": f"Cytat {slug}.",
    }


def _passage(passage_id: str, source_id: str, text: str) -> Passage:
    return Passage(
        passage_id=passage_id,
        source_id=source_id,
        text=text,
        published_on=date(2026, 11, 1),
        fetched_at=AT,
    )


def _snapshot() -> SnapshotCorpus:
    return SnapshotCorpus(
        version=VERSION,
        taken_at=AT,
        urls={
            "doc-a": "https://www.gov.pl/a",
            # Stored with a trailing slash: still the golden source b.
            "doc-b": "https://www.gov.pl/b/",
            "doc-x": "https://example.pl/obcy",
        },
        passages=(
            _passage("p-a", "doc-a", "pierwszy"),
            _passage("p-b", "doc-b", "drugi"),
            _passage("p-x", "doc-x", "obcy"),
        ),
    )


class _Fake:
    """Embeds each text as the vector it is mapped to and counts the texts."""

    def __init__(self, vectors: dict[str, Vector]) -> None:
        self._vectors = vectors
        self.embedded: list[str] = []
        self.batches: list[int] = []

    async def embed_query(self, text: str) -> Vector:
        self.embedded.append(text)
        return self._vectors[text]

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        self.embedded.extend(texts)
        self.batches.append(len(texts))
        return [self._vectors[text] for text in texts]


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "e.toml"
    path.write_text(CONFIG.format(name="e"), encoding="utf-8")
    return path


def _cases(case: Make[GoldenCase]) -> GoldenSet:
    return GoldenSet.model_validate(
        [
            case(id="D-own-a", main_claim="Strefa A", sources=[_source("a")]),
            case(id="D-own-b", main_claim="Strefa B", sources=[_source("b")]),
            # A repeat of the same claim is one query, not a second vote.
            case(id="D-own-a-again", main_claim="Strefa A", sources=[_source("a")]),
            # Its source is not in the snapshot: it cannot be found at all.
            case(id="D-own-c", main_claim="Strefa C", sources=[_source("c")]),
            case(id="D-own-none", main_claim="Bez źródeł"),
        ]
    )


def test_golden_sources_are_the_targets_in_the_snapshot(
    tmp_path: Path, case: Make[GoldenCase]
) -> None:
    config = load_embeddings_config(_config(tmp_path))

    score = asyncio.run(
        score_retrieval(_cases(case), _snapshot(), config, _Fake(VECTORS))
    )

    assert (score.queries, score.queries_with_targets) == (3, 2)
    assert (score.documents, score.passages, score.top_k) == (3, 3, 20)
    # A finds its source first; B finds a, then the stranger x, then b.
    assert score.hit_rate == pytest.approx(1.0)
    assert score.mean_reciprocal_rank == pytest.approx((1 + 1 / 3) / 2, abs=1e-4)


def test_a_target_below_top_k_is_a_miss(tmp_path: Path, case: Make[GoldenCase]) -> None:
    config = load_embeddings_config(_config(tmp_path))

    score = asyncio.run(
        score_retrieval(_cases(case), _snapshot(), config, _Fake(VECTORS), top_k=2)
    )

    assert score.hit_rate == pytest.approx(0.5)
    assert score.mean_reciprocal_rank == pytest.approx(0.5)


def test_each_passage_is_embedded_and_paid_for_once(
    tmp_path: Path, case: Make[GoldenCase]
) -> None:
    config = load_embeddings_config(_config(tmp_path))
    fake = _Fake(VECTORS)

    score = asyncio.run(score_retrieval(_cases(case), _snapshot(), config, fake))

    assert sorted(fake.embedded) == sorted(
        ["Strefa A", "Strefa B", "pierwszy", "drugi", "obcy"]
    )
    # C has no target to find, so it is not embedded: 2 * 8 query chars and
    # 8 + 5 + 4 passage chars, at 2 USD per million chars.
    assert score.characters == 33
    assert score.cost_usd == pytest.approx(33 * 2 / 1_000_000)
    assert score.cost_100_queries_usd == pytest.approx(800 * 2 / 1_000_000)


def test_comparison_names_the_snapshot_and_keeps_config_order(
    tmp_path: Path, case: Make[GoldenCase]
) -> None:
    config = load_embeddings_config(_config(tmp_path))
    score = asyncio.run(
        score_retrieval(_cases(case), _snapshot(), config, _Fake(VECTORS))
    )

    comparison = compare_embeddings([score, score], "cases.json", VERSION, AT)

    assert comparison.generated_at == AT
    assert comparison.corpus == VERSION
    assert [m.name for m in comparison.models] == ["e", "e"]
    assert comparison.models[0].provider == "stub"


def test_a_snapshot_file_reads_back_the_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text(_snapshot().model_dump_json(), encoding="utf-8")

    assert load_snapshot_file(path) == _snapshot()


REPO = Path(__file__).parents[2]
CANDIDATE = str(REPO / "evals" / "embeddings" / "gemini-embedding-001.toml")


def test_compare_embeddings_needs_a_snapshot(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("MERITUM_CORPUS_DATABASE_URL", raising=False)

    with pytest.raises(SystemExit):
        meritum_eval(["--compare-embeddings", CANDIDATE])

    assert "--corpus-version or --corpus-file" in capsys.readouterr().err


def test_a_snapshot_file_of_another_version_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text(_snapshot().model_dump_json(), encoding="utf-8")
    argv = ["--compare-embeddings", CANDIDATE, "--corpus-file", str(path)]

    with pytest.raises(SystemExit):
        meritum_eval([*argv, "--corpus-version", "2026-11-21T04:00Z"])

    assert f"holds snapshot {VERSION}" in capsys.readouterr().err


@pytest.mark.parametrize(
    "path", sorted(Path(__file__).parents[2].glob("evals/embeddings/*.toml")), ids=str
)
def test_repo_embeddings_configs_are_valid(path: Path) -> None:
    assert load_embeddings_config(path).name == path.stem


def test_passages_are_embedded_in_batches_like_ingest() -> None:
    texts = [f"tekst {i}" for i in range(250)]
    fake = _Fake(dict.fromkeys(texts, (3.0, 4.0)))
    metered = MeteredEmbeddings(fake)

    vectors = asyncio.run(metered.embed_documents([*texts, *texts]))

    assert fake.batches == [100, 100, 50]
    assert vectors[0] == pytest.approx((0.6, 0.8))
    assert len(vectors) == len(texts) * 2
