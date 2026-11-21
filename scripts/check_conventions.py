"""Check the Meritum conventions that Ruff, ty and pytestarch cannot express.

Run ``uv run python scripts/check_conventions.py`` (CI: lint job). The same file
lives in meritum-core, meritum-backend and meritum-worker; per-repo settings and
every exception (path = reason) are in ``[tool.meritum-conventions]`` in
pyproject.toml. The checks are listed in docs/architecture.md.
"""

import ast
import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCANNED_DIRS = ("src", "tests", "scripts", "features")
FEATURE_ID = re.compile(r"^(US-[A-Z]{3}-\d{2}|F-\d{2}|ADR-\d{2})$")
NO_FEATURE = "none (infrastructure)"
CONSTANT_NAME = re.compile(r"^_?[A-Z][A-Z0-9_]*$")
ENTRY_NAME = re.compile(r"^\**(\w+)\s*(\([^)]*\))?:")
Problems = Iterator[tuple[int, str]]
Function = ast.FunctionDef | ast.AsyncFunctionDef


def load_config() -> dict[str, Any]:
    """Read ``[tool.meritum-conventions]``.

    Returns:
        The table; exception tables map a relative path to its reason.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)["tool"]["meritum-conventions"]


def section(doc: str, name: str) -> list[str] | None:
    """Return the stripped lines of a Google-style section, None when absent.

    Args:
        doc: the cleaned docstring.
        name: the section name without the colon, e.g. ``Args``.

    Returns:
        The non-empty lines, the header's own text first.
    """
    lines = doc.splitlines()
    for index, line in enumerate(lines):
        head = line.strip()
        if head != f"{name}:" and not head.startswith(f"{name}: "):
            continue
        indent = len(line) - len(line.lstrip())
        body = [head.removeprefix(f"{name}:")]
        for nxt in lines[index + 1 :]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        return [entry.strip() for entry in body if entry.strip()]
    return None


def feature_problems(doc: str, *, required: bool) -> list[str]:
    """Check the ``Features:`` section of one docstring.

    Args:
        doc: the cleaned docstring.
        required: whether a missing section is a problem.

    Returns:
        Problem descriptions, empty when the section is fine.
    """
    entries = section(doc, "Features")
    if entries is None:
        return ["missing `Features:` section"] if required else []
    text = " ".join(entries)
    ids = [token for token in re.split(r"[,\s]+", text) if token]
    bad = [token for token in ids if not FEATURE_ID.match(token)]
    if text != NO_FEATURE and (bad or not ids):
        return [f"bad `Features:` entry {text!r} (US-XXX-00, F-00, ADR-00)"]
    return []


def _public(name: str) -> bool:
    return not name.startswith("_")


def _missing(owner: str, doc: str, name: str, expected: list[str]) -> Problems:
    entries = section(doc, name) or []
    listed = {m.group(1) for m in map(ENTRY_NAME.match, entries) if m}
    if absent := [item for item in expected if item not in listed]:
        yield 0, f"{owner}: document {absent} under `{name}:`"


def _params(func: Function) -> list[str]:
    args = func.args
    names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    names += [a.arg for a in (args.vararg, args.kwarg) if a is not None]
    return [n for n in names if _public(n) and n not in {"self", "cls"}]


def _check_function(func: Function, *, top: bool, class_doc: str | None) -> Problems:
    own_doc = ast.get_docstring(func) or ""
    args_doc = class_doc if func.name == "__init__" else own_doc
    if args_doc is None or not (_public(func.name) or func.name == "__init__"):
        return
    for _, problem in _missing(func.name, args_doc, "Args", _params(func)):
        yield func.lineno, problem
    for problem in feature_problems(own_doc, required=top):
        yield func.lineno, f"{func.name}: {problem}"


def _check_class(cls: ast.ClassDef, *, top: bool) -> Problems:
    doc = ast.get_docstring(cls) or ""
    targets = [s.target for s in cls.body if isinstance(s, ast.AnnAssign)]
    fields = [t.id for t in targets if isinstance(t, ast.Name) and _public(t.id)]
    for _, problem in _missing(cls.name, doc, "Attributes", fields):
        yield cls.lineno, problem
    for problem in feature_problems(doc, required=top):
        yield cls.lineno, f"{cls.name}: {problem}"
    for node in cls.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield from _check_function(node, top=False, class_doc=doc)
        elif isinstance(node, ast.ClassDef) and _public(node.name):
            yield from _check_class(node, top=False)


def _check_constants(body: list[ast.stmt], *, allowed_here: bool) -> Problems:
    for index, node in enumerate(body):
        targets = node.targets if isinstance(node, ast.Assign) else []
        annotation = ""
        if isinstance(node, ast.AnnAssign):
            targets, annotation = [node.target], ast.unparse(node.annotation)
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        nxt = body[index + 1] if index + 1 < len(body) else None
        value = nxt.value if isinstance(nxt, ast.Expr) else None
        has_doc = isinstance(value, ast.Constant) and isinstance(value.value, str)
        for name in filter(CONSTANT_NAME.match, names):
            if not allowed_here:
                yield node.lineno, f"constant {name} belongs in constants.py"
            if "Final" not in annotation:
                yield node.lineno, f"constant {name} must be annotated Final"
            if not has_doc:
                yield node.lineno, f"constant {name} needs an attribute docstring"


def check_src_module(tree: ast.Module, *, constants_allowed: bool) -> Problems:
    """Run the docstring and constant checks on one src module.

    Args:
        tree: the parsed module.
        constants_allowed: whether the module may define constants.

    Yields:
        (line, message) pairs.
    """
    for problem in feature_problems(ast.get_docstring(tree) or "", required=False):
        yield 1, problem
    yield from _check_constants(tree.body, allowed_here=constants_allowed)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and _public(node.name):
            yield from _check_class(node, top=True)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield from _check_function(node, top=True, class_doc=None)


def _scope(module: str, name: str, src: Path) -> str:
    # The package allowed to import a private part of `module` ('' if public).
    parts = module.split(".")
    private = next((i for i, p in enumerate(parts) if p.startswith("_")), None)
    if private is not None:
        return ".".join(parts[:private])
    if not name.startswith("_") or name.startswith("__"):
        return ""
    is_file = src.joinpath(*parts).with_suffix(".py").is_file()
    return module.rpartition(".")[0] if is_file else module


def check_private_imports(tree: ast.Module, importer: str, src: Path) -> Problems:
    """Find imports of another package's private modules or names.

    Args:
        tree: the parsed module.
        importer: the dotted name of the importing module.
        src: the src directory (tells modules from packages).

    Yields:
        (line, message) pairs.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = [(alias.name, "") for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:  # level 0: absolute
            imported = [(node.module or "", alias.name) for alias in node.names]
        else:
            continue
        for module, name in imported:
            scope = _scope(module, name, src)
            if scope and not f"{importer}.".startswith(f"{scope}."):
                yield node.lineno, f"private import {module} {name}".rstrip()


def check_file(path: Path, config: dict[str, Any]) -> list[str]:
    """Run every check that applies to one file.

    Args:
        path: an absolute path under the repository root.
        config: the ``[tool.meritum-conventions]`` table.

    Returns:
        ``path:line: message`` strings.
    """
    rel = path.relative_to(ROOT).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=rel)
    in_src = rel.startswith("src/")
    module = ".".join(Path(rel.removeprefix("src/")).with_suffix("").parts)
    problems = list(check_private_imports(tree, module, ROOT / "src"))
    lines, limit = len(source.splitlines()), config["max-lines"]
    if lines > limit and rel not in config.get("line-limit-exceptions", {}):
        problems.append((1, f"{lines} lines, limit {limit}: split the module"))
    if in_src and rel not in config.get("module-exceptions", {}):
        allowed = path.name == "constants.py" or rel in config.get(
            "constants-exceptions", {}
        )
        problems += check_src_module(tree, constants_allowed=allowed)
    init = path.parent / "__init__.py"
    is_private = path.name.startswith("_") and path.name != "__init__.py"
    if in_src and is_private and "__all__" not in init.read_text(encoding="utf-8"):
        problems.append((1, "the package __init__.py must declare __all__"))
    return [f"{rel}:{line}: {message}" for line, message in problems]


def main() -> int:
    """Check the repository and print every problem.

    Returns:
        The exit code: 0 when clean, 1 otherwise.
    """
    config = load_config()
    files = sorted(p for d in SCANNED_DIRS for p in (ROOT / d).rglob("*.py"))
    problems = [problem for path in files for problem in check_file(path, config)]
    sys.stdout.write("".join(f"{problem}\n" for problem in problems))
    sys.stdout.write(f"conventions: {len(problems)} problem(s)\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
