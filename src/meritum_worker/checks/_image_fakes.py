"""In-process fakes of image reading for tests and behave: no network.

Features:
    US-SPR-08, F-33
"""

import tempfile
from pathlib import Path
from typing import TypedDict

from meritum_core.checks.ocr import (
    ImageSearchPort,
    OcrPort,
    OcrSettings,
    build_image_search,
    build_ocr,
)
from meritum_core.checks.ocr.constants import PNG_MAGIC
from meritum_core.shared.blobs import (
    BlobProvider,
    BlobSettings,
    BlobStore,
    build_blob_store,
)


def png() -> bytes:
    """Build the smallest file ``inspect_image`` reads as a PNG; no pixels.

    Returns:
        The file's bytes.

    Features:
        US-SPR-08, F-33
    """
    return PNG_MAGIC + bytes(16)


class ImagePorts(TypedDict):
    """The CheckDeps ports of an image check, for ``CheckDeps(**image_ports())``.

    Attributes:
        blobs: the in-memory store of the images.
        ocr: the core stub OCR over that store.
        image_search: the search that reports it did not run.

    Features:
        US-SPR-08, F-33
    """

    blobs: BlobStore
    ocr: OcrPort
    image_search: ImageSearchPort


def image_ports(text: str | None = None) -> ImagePorts:
    """An in-memory blob store, the core stub OCR over it and no image search.

    Args:
        text: what the stub reads from every supported image; None makes every
            read fail as the provider would.

    Returns:
        The ports.

    Features:
        US-SPR-08, F-33
    """
    blobs = build_blob_store(BlobSettings(provider=BlobProvider.MEMORY))
    fixture = None
    if text is not None:
        fixture = Path(tempfile.mkdtemp()) / "ocr.txt"
        fixture.write_text(text, encoding="utf-8")
    ocr = build_ocr(OcrSettings(stub_text=fixture), blobs)
    return ImagePorts(blobs=blobs, ocr=ocr, image_search=build_image_search())
