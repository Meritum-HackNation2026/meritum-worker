"""The integration marker is registered and the default run (CI) skips it."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_integration_marker_is_registered_and_off_by_default() -> None:
    pytest_config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"][
        "pytest"
    ]
    assert any(m.startswith("integration:") for m in pytest_config["markers"])
    assert pytest_config["addopts"][-2:] == ["-m", "not integration"]
