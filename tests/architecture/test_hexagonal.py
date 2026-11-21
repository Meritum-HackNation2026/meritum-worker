"""Hexagonal architecture: domain code never imports adapters or frameworks.

Domain means every module outside ``WIRING`` (adapters, factories, app wiring);
the settings are in conftest.py.
"""

from collections.abc import Callable

type Forbid = Callable[[list[str], list[str]], None]


def test_domain_never_imports_frameworks(
    domain: list[str], frameworks: list[str], forbid: Forbid
) -> None:
    forbid(domain, frameworks)


def test_domain_never_imports_adapters(
    domain: list[str], adapters: list[str], forbid: Forbid
) -> None:
    forbid(domain, adapters)
