"""BlobCaseSets reads a user file from BlobStore (US-OBS-06, core#124)."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from meritum_core.shared.blobs import (
    BlobKind,
    BlobProvider,
    BlobSettings,
    BlobStore,
    build_blob_store,
)

from meritum_worker.observability.adapters import BlobCaseSets
from meritum_worker.observability.golden import load_golden_set
from meritum_worker.observability.models import GoldenSet

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = load_golden_set(ROOT / "evals" / "golden" / "cases.json")


def _memory_store() -> BlobStore:
    return build_blob_store(BlobSettings(provider=BlobProvider.MEMORY))


async def _store_cases(store: BlobStore, cases: GoldenSet) -> str:
    data = json.dumps(
        [case.model_dump(mode="json") for case in cases.root]
    ).encode()
    ref = await store.put(
        data,
        kind=BlobKind.DATASET,
        content_type="application/json",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    return ref.blob_id


def test_a_user_file_is_read_from_the_blob_store() -> None:
    store = _memory_store()
    own = GoldenSet(GOLDEN.root[:30])
    blob_id = asyncio.run(_store_cases(store, own))
    sets = BlobCaseSets(ROOT / "evals" / "golden" / "cases.json", store)
    loaded = asyncio.run(sets.load("user_file", "jury.json", dataset_blob_id=blob_id))
    assert [c.id for c in loaded.root] == [c.id for c in own.root]


def test_a_missing_blob_is_not_found() -> None:
    sets = BlobCaseSets(ROOT / "evals" / "golden" / "cases.json", _memory_store())
    with pytest.raises(LookupError):
        asyncio.run(
            sets.load(
                "user_file",
                "jury.json",
                dataset_blob_id="dataset_00000000000000000000000000000000",
            )
        )
