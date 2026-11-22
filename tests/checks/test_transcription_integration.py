"""Real Chirp 3 on a Discord voice message: local only (-m integration).

Set ``MERITUM_TRANSCRIPTION_PROVIDER=speech_v2`` and its variables as in the
README, and ``MERITUM_TEST_AUDIO_FILE`` to an OGG Opus 48 kHz file saved from
Discord; without them it skips.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from meritum_core.checks.transcription import (
    TranscriptionProvider,
    TranscriptionSettings,
    build_transcriber,
)
from meritum_core.shared.blobs import BlobKind, BlobSettings, build_blob_store


@pytest.mark.integration
def test_chirp_decodes_discord_ogg_opus_without_conversion() -> None:
    path = os.environ.get("MERITUM_TEST_AUDIO_FILE")
    settings = TranscriptionSettings()
    if path is None or settings.provider is not TranscriptionProvider.SPEECH_V2:
        pytest.skip("MERITUM_TEST_AUDIO_FILE or speech_v2 is not set")
    blobs = build_blob_store(BlobSettings())
    ref = asyncio.run(
        blobs.put(
            Path(path).read_bytes(),
            kind=BlobKind.AUDIO,
            content_type="audio/ogg",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    transcript = asyncio.run(build_transcriber(settings, blobs).transcribe(ref.blob_id))
    asyncio.run(blobs.delete(ref.blob_id))
    assert transcript.text.strip()
