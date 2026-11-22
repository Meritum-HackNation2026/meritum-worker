"""scripts/check_conventions.py: the repo is clean and the checks catch violations."""

import ast
import runpy
from pathlib import Path
from textwrap import dedent

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "scripts" / "check_conventions.py"))


def problems(source: str, *, constants_allowed: bool = False) -> list[str]:
    tree = ast.parse(dedent(source))
    found = CHECKER["check_src_module"](tree, constants_allowed=constants_allowed)
    return [message for _, message in found]


def test_repository_follows_the_conventions() -> None:
    config = CHECKER["load_config"]()
    files = sorted(p for d in CHECKER["SCANNED_DIRS"] for p in (ROOT / d).rglob("*.py"))
    found = [p for path in files for p in CHECKER["check_file"](path, config)]
    assert found == []


def test_documented_function_passes() -> None:
    source = '''
        def run(text: str, *, limit: int = 3) -> str:
            """Run.

            Args:
                text: input.
                limit (int): cap.

            Returns:
                Output.

            Features:
                US-SPR-01, ADR-03
            """
    '''
    assert problems(source) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('def run(x: int) -> None:\n    """Run."""', "missing `Features:`"),
        (
            'def run() -> None:\n    """Run.\n\n    Features:\n        X-1\n    """',
            "bad",
        ),
        (
            'def run(x: int) -> None:\n    """Run.\n\n    Features: F-01\n    """',
            "document ['x'] under `Args:`",
        ),
        (
            'class A:\n    """A.\n\n    Features: F-01\n    """\n\n    name: str',
            "document ['name'] under `Attributes:`",
        ),
        ('LIMIT: Final = 3\n"""Cap."""', "belongs in constants.py"),
        ("LIMIT = 3", "needs an attribute docstring"),
        ('LIMIT = 3\n"""Cap."""', "must be annotated Final"),
    ],
)
def test_violations_are_reported(source: str, expected: str) -> None:
    assert any(expected in message for message in problems(source))


def test_constants_module_may_hold_documented_constants() -> None:
    source = 'LIMIT: Final = 3\n"""Cap."""'
    assert problems(source, constants_allowed=True) == []


def test_private_imports_across_packages_are_reported(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").touch()
    source = dedent("""
        from pkg._impl import thing
        from pkg.mod import _helper
        import pkg._impl
        from pkg import public, __version__
    """)
    found = CHECKER["check_private_imports"](ast.parse(source), "other.x", tmp_path)
    assert [line for line, _ in found] == [2, 3, 4]
    inside = CHECKER["check_private_imports"](ast.parse(source), "pkg.y", tmp_path)
    assert list(inside) == []
