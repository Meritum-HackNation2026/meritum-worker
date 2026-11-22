"""meritum-worker-migrate: core app migrations always, corpus only with --corpus."""

import pytest

from meritum_worker import main

URL = "postgresql://worker@db/meritum?options=-csearch_path%3Dapp_dev"


@pytest.fixture
def ran(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    monkeypatch.setenv("MERITUM_DATABASE_URL", URL)
    monkeypatch.setenv("MERITUM_ENV", "dev")
    monkeypatch.setattr(
        main, "apply_migrations", lambda url: calls.append(("app", url)) or ["1.sql"]
    )
    monkeypatch.setattr(
        main, "apply_corpus_migrations", lambda url: calls.append(("corpus", url)) or []
    )
    return calls


def test_without_corpus_flag_only_app_schema_is_migrated(
    ran: list[tuple[str, str]], capsys: pytest.CaptureFixture[str]
) -> None:
    main.migrate([])
    assert ran == [("app", URL)]
    assert capsys.readouterr().out == "app_dev: 1.sql\n"


def test_corpus_flag_migrates_corpus_after_app(
    ran: list[tuple[str, str]], capsys: pytest.CaptureFixture[str]
) -> None:
    main.migrate(["--corpus"])
    assert ran == [("app", URL), ("corpus", URL)]
    assert capsys.readouterr().out == "app_dev: 1.sql\ncorpus: up to date\n"


def test_failed_migration_exits_with_its_name(
    ran: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_url: str) -> list[str]:
        msg = "0002_x.sql: syntax error\nLINE 3: CREAT TABLE\n        ^"
        raise RuntimeError(msg)

    monkeypatch.setattr(main, "apply_migrations", fail)
    with pytest.raises(SystemExit) as exited:
        main.migrate(["--corpus"])
    # one line: the deploy shows the last line of the output as its error
    assert exited.value.code == (
        "migration app_dev failed: 0002_x.sql: syntax error LINE 3: CREAT TABLE ^"
    )
    assert ran == []


@pytest.mark.parametrize(
    ("environment", "provider", "expected"),
    [
        ("local", "postgres", [("app", URL)]),
        ("local", "memory", []),
        ("dev", "postgres", []),
        ("prd", "postgres", []),
    ],
)
def test_worker_migrates_local_postgres_before_starting_dbos(
    ran: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    provider: str,
    expected: list[tuple[str, str]],
) -> None:
    class DBOSStartError(Exception):
        """Stop at the first DBOS operation."""

    def start(**_kwargs: object) -> None:
        raise DBOSStartError

    monkeypatch.setenv("MERITUM_ENV", environment)
    monkeypatch.setenv("MERITUM_DATABASE_PROVIDER", provider)
    monkeypatch.setattr(main, "DBOS", start)
    with pytest.raises(DBOSStartError):
        main.main()
    assert ran == expected
