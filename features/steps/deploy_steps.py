"""Steps for features/deploy.feature: deploy/deploy.sh with a fake docker."""

import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tempfile
from pathlib import Path

from behave import given, then, when
from behave.runner import Context

DEPLOY = Path(__file__).resolve().parents[2] / "deploy" / "deploy.sh"
BRANCHES = {"dev": "develop", "prd": "main"}
# Records argv; the migration command fails when FAIL_MIGRATION names a schema.
FAKE_DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >>"$CALLS"
case "$*" in
  *meritum-worker-migrate*)
    if [ -n "${FAIL_MIGRATION:-}" ]; then
      echo "migration $FAIL_MIGRATION failed: syntax error" >&2; exit 1
    fi ;;
  logs*) echo 'meritum-worker ready' ;;
esac
"""


@given("nową migrację tabel aplikacji i nową migrację schematu corpus")
def new_app_and_corpus_migrations(context: Context) -> None:
    context.fail_migration = ""


@given("migrację app_dev, która kończy się błędem")
def failing_app_migration(context: Context) -> None:
    context.fail_migration = "app_dev"


@when('deploy workera "{env}" startuje')
def deploy_starts(context: Context, env: str) -> None:
    tmp = Path(tempfile.mkdtemp())
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    for name, body in (("docker", FAKE_DOCKER), ("flock", "#!/bin/sh\n")):
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    (tmp / "envs").mkdir()
    (tmp / "envs" / f"worker-{env}.env").write_text("")
    calls = tmp / "calls"
    calls.touch()
    done = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [str(DEPLOY), BRANCHES[env], "0" * 40],
        env={
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp),
            "M_STATE": str(tmp),
            "CALLS": str(calls),
            "CORE_KEY_FILE": "/dev/null",
            "FAIL_MIGRATION": context.fail_migration,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    context.code = done.returncode
    context.log = done.stdout + done.stderr
    context.calls = calls.read_text().splitlines()


def migrations(context: Context) -> list[str]:
    return [c for c in context.calls if "meritum-worker-migrate" in c]


def index_of(context: Context, prefix: str) -> int:
    return next(i for i, c in enumerate(context.calls) if c.startswith(prefix))


@then("migracja app jest uruchomiona, a migracja corpus nie")
def app_without_corpus(context: Context) -> None:
    assert context.code == 0, context.log
    assert len(migrations(context)) == 1
    assert "--corpus" not in migrations(context)[0]


@then("log deployu mówi, że migracje corpus uruchamia tylko main")
def log_says_corpus_only_from_main(context: Context) -> None:
    assert "corpus migrations run only from main" in context.log


@then("migracje app i corpus są uruchomione, zanim wystartuje nowy kontener")
def app_and_corpus_before_swap(context: Context) -> None:
    assert context.code == 0, context.log
    [migrate] = migrations(context)
    assert migrate.endswith("meritum-worker-migrate --corpus")
    assert context.calls.index(migrate) < index_of(context, "rm -f")


@then(
    'stary kontener działa dalej, a deploy kończy się błędem z nazwą migracji "{name}"'
)
def old_container_keeps_running(context: Context, name: str) -> None:
    assert context.code != 0
    assert not any(c.startswith(("rm -f", "run -d")) for c in context.calls)
    assert f"::error title=Migration failed::migration {name} failed" in context.log
