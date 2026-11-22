"""pytestarch setup for the architecture tests; the per-repo settings are here.

test_hexagonal.py and test_slices.py are the same in core, backend and worker.
"""

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from pytestarch import EvaluableArchitecture, Rule, get_evaluable_architecture

PACKAGE = "meritum_worker"
# Modules that may use frameworks and adapters: main registers the workflows with
# DBOS and runs them; workflow bodies (jobs) stay plain functions.
# Fakes stand in for external services, so they may use the HTTP client's mock
# transport like the adapters they replace.
# A subdomain (corpus.ready) has its own adapters, factory and fakes.
WIRING = re.compile(
    r"^meritum_worker\.(main|[a-z_]+(\.[a-z_]+)?\.(adapters|factory|fakes))(\.|$)"
)
FRAMEWORKS = re.compile(
    r"^(dbos|fastapi|starlette|slowapi|psycopg|uvicorn|httpx2?|cryptography)(\.|$)"
)
ADAPTERS = re.compile(r"^meritum_[a-z]+(\.[a-z_]+)*\.adapters(\.|$)")

type Forbid = Callable[[list[str], list[str]], None]


@pytest.fixture(scope="session")
def evaluable() -> EvaluableArchitecture:
    src = Path(__file__).resolve().parents[2] / "src" / PACKAGE
    return get_evaluable_architecture(src, src, exclude_external_libraries=False)


@pytest.fixture(scope="session")
def modules(evaluable: EvaluableArchitecture) -> list[str]:
    """Every module in the graph, external ones included."""
    return sorted(evaluable.modules)


@pytest.fixture(scope="session")
def own(modules: list[str]) -> list[str]:
    """This package's modules; packages appear as their ``__init__``."""
    packages = {m.removesuffix(".__init__") for m in modules if m.endswith(".__init__")}
    return [m for m in modules if m.startswith(f"{PACKAGE}.") and m not in packages]


@pytest.fixture(scope="session")
def domain(own: list[str]) -> list[str]:
    """Modules that must stay framework- and adapter-free."""
    return [m for m in own if not WIRING.match(m)]


@pytest.fixture(scope="session")
def frameworks(modules: list[str]) -> list[str]:
    """Framework modules the domain must not import."""
    return [m for m in modules if FRAMEWORKS.match(m)]


@pytest.fixture(scope="session")
def adapters(modules: list[str]) -> list[str]:
    """Adapter modules of this repo and of meritum-core."""
    return [m for m in modules if ADAPTERS.match(m)]


type Boundaries = list[tuple[list[str], list[str]]]


@pytest.fixture(scope="session")
def slice_boundaries(own: list[str]) -> Boundaries:
    """Per slice: (modules outside it except wiring, its non-``__init__`` modules)."""
    boundaries: Boundaries = []
    for name in sorted({m.split(".")[1] for m in own if m.count(".") > 1}):
        inside = f"{PACKAGE}.{name}."
        internals = [m for m in own if m.startswith(inside) and "__init__" not in m]
        outside = [m for m in own if not m.startswith(inside) and not WIRING.match(m)]
        boundaries.append((outside, internals))
    return boundaries


@pytest.fixture(scope="session")
def private_boundaries(own: list[str]) -> Boundaries:
    """Per private ``_x`` module: (modules outside its package, [the module])."""
    private = [m for m in own if "._" in m and not m.endswith("__init__")]
    return [
        ([o for o in own if not o.startswith(m[: m.index("._") + 1])], [m])
        for m in private
    ]


@pytest.fixture(scope="session")
def forbid(evaluable: EvaluableArchitecture) -> Forbid:
    """Assert that no module of ``importers`` imports one of ``imported``."""

    def exactly(names: list[str]) -> str:
        return "^(" + "|".join(map(re.escape, names)) + ")$"

    def check(importers: list[str], imported: list[str]) -> None:
        if importers and imported:
            rule = Rule().modules_that().have_name_matching(exactly(importers))
            rule.should_not().import_modules_that().have_name_matching(
                exactly(imported)
            ).assert_applies(evaluable)

    return check
