"""deploy/deploy.sh mounts every MERITUM_GCP_MOUNTS entry read-only."""

from pathlib import Path

from tests.test_deploy_secrets import deploy, needs_posix, started

pytestmark = needs_posix

WORKER = "/home/m/meritum/gcp/meritum-worker:/var/run/meritum/gcp/meritum-worker:ro"
SPEECH = "/home/m/meritum/gcp/meritum-speech:/var/run/meritum/gcp/meritum-speech:ro"


def test_every_gcp_mount_entry_is_mounted(tmp_path: Path) -> None:
    calls, _ = deploy(tmp_path, {}, f"MERITUM_GCP_MOUNTS={WORKER} {SPEECH}\n")
    run = started(calls)
    assert f"-v {WORKER} " in run
    assert f"-v {SPEECH} " in run


def test_no_gcp_mount_without_entry_in_env_file(tmp_path: Path) -> None:
    calls, log = deploy(tmp_path, {})
    assert "/gcp/" not in started(calls)
    assert "without GCP credentials" in log


def test_gcp_mount_without_read_only_is_skipped(tmp_path: Path) -> None:
    calls, log = deploy(tmp_path, {}, f"MERITUM_GCP_MOUNTS=/h/gcp:/etc/gcp {SPEECH}\n")
    run = started(calls)
    assert "/h/gcp" not in run
    assert f"-v {SPEECH} " in run
    assert "::warning title=GCP mount skipped::/h/gcp:/etc/gcp is not :ro" in log
