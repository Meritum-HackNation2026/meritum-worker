"""In-process fakes for tests and behave: no DBOS, no database, no network.

Features:
    US-SPR-01, US-SPR-07, F-06, F-22
"""

from pathlib import Path
from typing import TypedDict, override

from meritum_core.checks import AnalysisStatus
from meritum_core.checks.transcription import (
    TranscriptionPort,
    TranscriptionSettings,
    build_transcriber,
)
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    PageFetchError,
)
from meritum_core.notifications import NotificationRepository
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from meritum_core.shared.blobs import (
    BlobProvider,
    BlobSettings,
    BlobStore,
    build_blob_store,
)

from meritum_worker.checks.models import CheckState
from meritum_worker.checks.ports import StepRun
from meritum_worker.corpus import FakeWebSearch
from meritum_worker.security import CleanInjectionDetector


class InlineCheckRuntime:
    """Runs each step at once and keeps every published status.

    State and statuses go through JSON, as DBOS keeps them, so a model that does
    not survive the round trip fails here too.

    Attributes:
        published: every AnalysisStatus, in order.
        step_names: the name of every step run, in order.
        closed_after: how many statuses were published when the stream closed;
            None while it is open.

    Features:
        US-SPR-01, US-SPR-02, F-22
    """

    def __init__(self) -> None:
        self.published: list[AnalysisStatus] = []
        self.step_names: list[str] = []
        self.closed_after: int | None = None

    async def step(self, name: str, run: StepRun, state: CheckState) -> CheckState:
        """Run the step on a JSON copy of the state.

        Args:
            name: the step's name.
            run: the step.
            state: its input.

        Returns:
            A JSON copy of the step's output.
        """
        self.step_names.append(name)
        output = await run(CheckState.model_validate_json(state.model_dump_json()))
        return CheckState.model_validate_json(output.model_dump_json())

    async def publish(self, status: AnalysisStatus) -> None:
        """Keep a JSON copy of ``status``.

        Args:
            status: the progress to publish.
        """
        self.published.append(
            AnalysisStatus.model_validate_json(status.model_dump_json())
        )

    async def close(self) -> None:
        """Close the progress stream and note how many statuses came before."""
        self.closed_after = len(self.published)


class FailingCheckRuntime(InlineCheckRuntime):
    """InlineCheckRuntime whose one named step raises RuntimeError("step failed").

    Args:
        failed_step: the name of the step that raises.

    Features:
        F-22
    """

    def __init__(self, failed_step: str) -> None:
        super().__init__()
        self._failed_step = failed_step

    @override
    async def step(self, name: str, run: StepRun, state: CheckState) -> CheckState:
        """Raise for the failing step, run any other one inline.

        Args:
            name: the step's name.
            run: the step.
            state: its input.

        Returns:
            A JSON copy of the step's output.

        Raises:
            RuntimeError: ``name`` is the failing step.
        """
        if name == self._failed_step:
            message = "step failed"
            raise RuntimeError(message)
        return await super().step(name, run, state)


class FakePageFetcher:
    """PageFetcherPort that answers every link with one page or one failure.

    Args:
        answer: the page, or the failure raised; None fails as unreachable.

    Attributes:
        calls: every fetched URL with its purpose, in order.

    Features:
        US-SPR-07, F-06
    """

    def __init__(
        self,
        answer: FetchedPage | PageFetchError | None = None,
    ) -> None:
        self.calls: list[tuple[str, FetchPurpose]] = []
        self._answer = answer or PageFetchError(FetchFailureReason.UNREACHABLE)

    async def fetch(self, url: str, *, purpose: FetchPurpose) -> FetchedPage:
        """Note the call and return the page, or raise the failure.

        Args:
            url: the link.
            purpose: why it is fetched.

        Returns:
            The page given at construction.

        Raises:
            PageFetchError: The failure given at construction (unreachable by default).
        """  # ruff: ignore[docstring-extraneous-exception]  # the failure is the stored instance
        self.calls.append((url, purpose))
        if isinstance(self._answer, PageFetchError):
            raise self._answer
        return self._answer


def ogg_opus(seconds: float) -> bytes:
    """Build the smallest Ogg Opus file ``inspect_audio`` reads as ``seconds`` long.

    Two Ogg pages: the first holds ``OpusHead``, the last states the length as
    a granule position in 48 kHz samples. No audio; the stub transcriber does
    not decode it.

    Args:
        seconds: the length the file states.

    Returns:
        The file's bytes.

    Features:
        US-SPR-11, F-08
    """
    header = b"OggS\x00\x02" + bytes(21) + b"\x13"  # 27-byte page header, 1 lacing byte
    last = b"OggS\x00\x04" + int(seconds * 48_000).to_bytes(8, "little") + bytes(13)
    return header + b"OpusHead" + bytes(11) + last


class AudioPorts(TypedDict):
    """The CheckDeps ports of a voice message, for ``CheckDeps(**audio_ports())``.

    Attributes:
        blobs: the in-memory store of the recordings.
        transcriber: the core stub transcriber over that store.
        notifications: the in-memory inbox.

    Features:
        US-SPR-11, US-POW-01, F-08
    """

    blobs: BlobStore
    transcriber: TranscriptionPort
    notifications: NotificationRepository


def audio_ports(transcript: Path | None = None) -> AudioPorts:
    """An in-memory blob store, the core stub transcriber over it and an inbox.

    Args:
        transcript: JSON file with the stub's ``Transcript``; None makes every
            transcription fail as the provider would.

    Returns:
        The ports.

    Features:
        US-SPR-11, US-POW-01, F-08
    """
    blobs = build_blob_store(BlobSettings(provider=BlobProvider.MEMORY))
    settings = TranscriptionSettings(stub_fixture=transcript)
    return AudioPorts(
        blobs=blobs,
        transcriber=build_transcriber(settings, blobs),
        notifications=InMemoryNotificationRepository(),
    )


class WebPorts(TypedDict):
    """The CheckDeps ports of live search, for ``CheckDeps(**web_ports())``.

    Attributes:
        web_search: a search that finds nothing.
        injection: a detector that finds nothing.
        catalog: an empty catalogue.

    Features:
        US-KOR-04, F-13
    """

    web_search: FakeWebSearch
    injection: CleanInjectionDetector
    catalog: tuple[()]


def web_ports() -> WebPorts:
    """Live search ports with no network: no results, nothing flagged.

    Returns:
        The ports.

    Features:
        US-KOR-04, F-13
    """
    search, detector = FakeWebSearch(), CleanInjectionDetector()
    return WebPorts(web_search=search, injection=detector, catalog=())
