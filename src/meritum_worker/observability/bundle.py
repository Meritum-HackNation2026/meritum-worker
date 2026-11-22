"""The meritum-eval-bundle command: the public bundle that reproduces a run.

The bundle holds the cases, their source addresses with cited fragments and
the snapshot manifest: each fetched page's id, address, SHA-256 of its main
text and fetched_at. Full texts and the cassette stay out (ADR-27); anyone can
refetch the pages and compare checksums (README).

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-27
"""

import argparse
import csv
import hashlib
from collections.abc import Sequence
from itertools import starmap
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict, TypeAdapter

from meritum_worker.observability.cases import load_eval_cases
from meritum_worker.observability.cassette import Cassette, PageTake
from meritum_worker.observability.constants import (
    BUNDLE_FILES,
    BUNDLE_NAME,
    DEFAULT_CASES_FILE,
)
from meritum_worker.observability.models import GoldenSet


class BundleSource(BaseModel):
    """A case's source as published: its address and the cited fragment.

    Attributes:
        case_id: The case citing it.
        url: Address of the source.
        publisher: Who published it.
        quote: The cited fragment, never the full text.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-27
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    url: str
    publisher: str
    quote: str


class ManifestDocument(BaseModel):
    """One page the run read, identified without its text.

    Attributes:
        document_id: The page's request key in the cassette.
        url: The final URL, after redirects.
        sha256: Hex SHA-256 of the page's main text, UTF-8.
        fetched_at: When the page was fetched.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-27
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    url: str
    sha256: str
    fetched_at: AwareDatetime


class Manifest(BaseModel):
    """The snapshot manifest of a recorded run.

    Attributes:
        corpus_version: The snapshot the run was pinned to.
        documents: Every page the run read, in recording order.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-27
    """

    model_config = ConfigDict(frozen=True)

    corpus_version: str
    documents: tuple[ManifestDocument, ...]


def meritum_eval_bundle(argv: Sequence[str] | None = None) -> None:
    """Write the public bundle of a recorded run to a folder.

    Args:
        argv: Command-line arguments; ``sys.argv`` when None.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-27
    """
    parser = argparse.ArgumentParser(prog=BUNDLE_NAME)
    parser.add_argument("--cases", type=Path, default=Path(DEFAULT_CASES_FILE))
    parser.add_argument("--cassette", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="bundle folder")
    args = parser.parse_args(argv)
    if args.cassette.resolve().is_relative_to(args.output.resolve()):
        parser.error("the cassette holds full texts: keep it outside the bundle")
    try:
        cases = load_eval_cases(args.cases)
        cassette = Cassette.load(args.cassette)
    except (OSError, TypeError, ValueError, csv.Error) as error:
        parser.error(str(error))
    sources = TypeAdapter(tuple[BundleSource, ...]).dump_json(_sources(cases), indent=2)
    contents = (
        cases.model_dump_json(indent=2),
        sources.decode(),
        _manifest(cassette).model_dump_json(indent=2),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in zip(BUNDLE_FILES, contents, strict=True):
        (args.output / name).write_text(content + "\n", encoding="utf-8")


def _sources(cases: GoldenSet) -> tuple[BundleSource, ...]:
    return tuple(
        BundleSource(
            case_id=case.id,
            url=str(source.url),
            publisher=source.publisher,
            quote=source.quote,
        )
        for case in cases.root
        for source in case.sources
    )


def _manifest(cassette: Cassette) -> Manifest:
    found = starmap(_document, cassette.pages.items())
    documents = tuple(document for document in found if document is not None)
    return Manifest(corpus_version=cassette.corpus_version, documents=documents)


def _document(key: str, takes: list[PageTake | None]) -> ManifestDocument | None:
    # The first page a URL gave; failed fetches read nothing, later takes repeat it.
    take = next((t for t in takes if t is not None and t.page is not None), None)
    if take is None or take.page is None:
        return None
    text = take.page.untrusted_text.encode()
    return ManifestDocument(
        document_id=key,
        url=take.page.url,
        sha256=hashlib.sha256(text).hexdigest(),
        fetched_at=take.fetched_at,
    )
