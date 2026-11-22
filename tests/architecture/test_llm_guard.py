"""No path to the model skips the injection shield (US-BEZ-01, F-19).

``run_check`` wraps ``deps.llm`` in ``ScreenedLlm`` before any step runs, so
every step reaches the model through it. A new module calling ``.complete``
must be added here on purpose: it either takes the model from ``CheckDeps``
(and so gets the shield) or is the shield or the eval cassette around it.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "meritum_worker"

# Modules allowed to call a model; each gets it from CheckDeps in run_check,
# or is the shield itself or the eval cassette that records the shielded model.
CALLERS = {
    "checks/steps/_extract_claims.py",
    "checks/steps/_write_answer.py",
    "evidence/reviews.py",
    "evidence/stance.py",
    "observability/adapters/_llm.py",
    "security/guard.py",
}


def _calls(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    ]


def test_only_known_modules_call_the_model() -> None:
    callers = {
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if _calls(ast.parse(path.read_text(encoding="utf-8")), "complete")
    }
    assert callers == CALLERS


def test_run_check_shields_the_model_before_any_step() -> None:
    tree = ast.parse((SRC / "checks" / "workflow.py").read_text(encoding="utf-8"))
    run_check = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_check"
    )
    assert _calls(run_check, "ScreenedLlm")
