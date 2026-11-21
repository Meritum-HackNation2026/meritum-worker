"""The default pytest run (CI) skips integration tests; -m integration runs them."""

# Runs pytest itself with the repo's config, from a fixed argv.
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
MARKED = "import pytest\n\n@pytest.mark.integration\ndef test_real_db():\n    pass\n"


def run_pytest(test_file: Path, *args: str) -> str:
    cmd = [sys.executable, "-m", "pytest", "-c", str(PYPROJECT), str(test_file), *args]
    done = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        cmd, capture_output=True, text=True, check=False
    )
    return done.stdout


@pytest.mark.parametrize(
    ("args", "summary"), [((), "1 deselected"), (("-m", "integration"), "1 passed")]
)
def test_integration_marker(
    tmp_path: Path, args: tuple[str, ...], summary: str
) -> None:
    test_file = tmp_path / "test_marked.py"
    test_file.write_text(MARKED, encoding="utf-8")
    assert summary in run_pytest(test_file, *args)
