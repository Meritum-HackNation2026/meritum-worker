"""behave steps call only the public API: no privates, adapters, wiring or DBOS."""

import ast
import re
from pathlib import Path

FEATURES = Path(__file__).resolve().parents[2] / "features"
FORBIDDEN = re.compile(
    r"^(dbos|meritum_worker\.main|meritum_[a-z]+(\.[a-z_]+)*\.adapters)(\.|$)|(^|\.)_[a-z]"
)


def imported_names(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names += [f"{node.module}.{alias.name}" for alias in node.names]
    return names


def test_steps_import_only_public_api() -> None:
    found = [
        f"{path.name}: {name}"
        for path in sorted(FEATURES.rglob("*.py"))
        for name in imported_names(path)
        if FORBIDDEN.search(name)
    ]
    assert found == []


def test_forbidden_imports_are_caught() -> None:
    bad = ["dbos.DBOS", "meritum_worker.main.env", "meritum_worker.checks._rule.x"]
    assert all(FORBIDDEN.search(name) for name in bad)
    assert not FORBIDDEN.search("meritum_worker.jobs")
