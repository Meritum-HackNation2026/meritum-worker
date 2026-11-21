"""Vertical slices: a slice uses another only via its package, never privates."""

from collections.abc import Callable

type Forbid = Callable[[list[str], list[str]], None]
type Boundaries = list[tuple[list[str], list[str]]]


def test_slices_import_each_other_only_through_their_package(
    slice_boundaries: Boundaries, forbid: Forbid
) -> None:
    for outside, internals in slice_boundaries:
        forbid(outside, internals)


def test_private_modules_are_imported_only_inside_their_package(
    private_boundaries: Boundaries, forbid: Forbid
) -> None:
    for outside, private in private_boundaries:
        forbid(outside, private)
