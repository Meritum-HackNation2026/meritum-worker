"""deploy/deploy.sh mounts the environment's files volume into the worker container."""

from pathlib import Path

from tests.test_deploy_secrets import deploy, started


def test_files_volume_is_mounted_under_files_dir(tmp_path: Path) -> None:
    env = (
        "MERITUM_FILES_VOLUME=meritum-files-dev\nMERITUM_FILES_DIR=/srv/meritum/files\n"
    )
    calls, _ = deploy(tmp_path, {}, env)
    assert "-v meritum-files-dev:/srv/meritum/files " in started(calls)


def test_no_mount_without_files_volume_in_env_file(tmp_path: Path) -> None:
    calls, _ = deploy(tmp_path, {})
    assert " -v " not in started(calls)
