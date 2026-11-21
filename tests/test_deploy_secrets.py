"""deploy/deploy.sh gives the repository secrets to the worker container by name."""

# Runs deploy.sh with fake docker and flock binaries that record their argv.
import os
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "deploy.sh"
CI = ROOT / ".github" / "workflows" / "ci.yml"
SECRET = "EUVSDISINFO_MCP_API_KEY"  # ruff: ignore[hardcoded-password-string] - a variable name, not a value
VALUE = "token-that-must-not-leak"
FAKE_DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >>"$CALLS"
if [ "$1" = logs ]; then echo 'meritum-worker ready'; fi
"""


def secret_names() -> list[str]:
    match = re.search(r"^worker_secrets=\(([^)]*)\)", DEPLOY.read_text(), re.MULTILINE)
    assert match, "deploy.sh has no worker_secrets=(...) list"
    names = match.group(1)
    assert isinstance(names, str)
    return names.split()


def deploy(tmp_path: Path, env: dict[str, str], env_file: str = "") -> tuple[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("docker", FAKE_DOCKER), ("flock", "#!/bin/sh\n")):
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    (tmp_path / "envs").mkdir()
    (tmp_path / "envs" / "worker-dev.env").write_text(env_file)
    calls = tmp_path / "calls"
    run_env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "M_STATE": str(tmp_path),
        "CALLS": str(calls),
        "CORE_KEY_FILE": "/dev/null",
        **env,
    }
    done = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [str(DEPLOY), "develop", "0" * 40],
        env=run_env,
        capture_output=True,
        text=True,
        check=True,
    )
    return calls.read_text(), done.stdout + done.stderr


def started(calls: str) -> str:
    return next(c for c in calls.splitlines() if c.startswith("run -d "))


def test_secret_is_passed_by_name_only(tmp_path: Path) -> None:
    calls, log = deploy(tmp_path, {SECRET: VALUE})
    assert f"-e {SECRET} " in started(calls)
    assert VALUE not in calls
    assert VALUE not in log
    assert [
        p
        for p in tmp_path.rglob("*")
        if p.is_file() and VALUE.encode() in p.read_bytes()
    ] == []


def test_missing_secret_still_starts_the_container(tmp_path: Path) -> None:
    calls, _ = deploy(tmp_path, {})
    assert f"-e {SECRET} " in started(calls)


@pytest.mark.parametrize("name", secret_names())
def test_ci_deploy_step_maps_every_listed_secret(name: str) -> None:
    # One shared secret, or one per env: <name>_PRD from main, <name>_DEV from develop.
    per_env = (
        f"{name}: ${{{{ secrets[format('{name}_{{0}}',"
        " github.ref_name == 'main' && 'PRD' || 'DEV')] }}"
    )
    ci = CI.read_text()
    assert f"{name}: ${{{{ secrets.{name} }}}}" in ci or per_env in ci


@pytest.mark.parametrize("name", secret_names())
def test_every_listed_secret_is_passed_by_name_only(tmp_path: Path, name: str) -> None:
    calls, log = deploy(tmp_path, {name: VALUE})
    assert f"-e {name}" in started(calls)
    assert VALUE not in calls + log
