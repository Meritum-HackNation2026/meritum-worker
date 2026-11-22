import pytest
from meritum_core.checks.adapters import PostgresCheckRecordRepository
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.shared.database import DatabaseProvider, DatabaseSettings
from meritum_core.shared.llm import LlmProvider, LlmSettings
from pydantic import SecretStr

from meritum_worker.checks.factory import build_check_deps

POSTGRES_URL = "postgresql://worker@db/meritum?options=-csearch_path%3Dapp_dev"


def test_check_deps_keep_records_in_memory_by_default() -> None:
    deps = build_check_deps(LlmSettings(provider=LlmProvider.STUB), DatabaseSettings())
    assert isinstance(deps.records, InMemoryCheckRecordRepository)


def test_check_deps_keep_records_in_postgres_when_configured() -> None:
    database = DatabaseSettings(
        provider=DatabaseProvider.POSTGRES, url=SecretStr(POSTGRES_URL)
    )
    deps = build_check_deps(LlmSettings(provider=LlmProvider.STUB), database)
    assert isinstance(deps.records, PostgresCheckRecordRepository)


def test_check_deps_hand_live_pages_to_the_corpus_only_where_ingestion_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = LlmSettings(provider=LlmProvider.STUB)
    monkeypatch.delenv("MERITUM_CORPUS_INGEST", raising=False)
    assert build_check_deps(stub, DatabaseSettings()).live_pages is None
    monkeypatch.setenv("MERITUM_CORPUS_INGEST", "enabled")
    assert build_check_deps(stub, DatabaseSettings()).live_pages is not None
