"""Answers of the gates compared only, never deployed: NLI and input classifier.

They have no adapter in the repo, so their runs are recorded to files.

Features:
    US-BEZ-01, US-OBS-04, US-SPR-06, F-07, F-27, ADR-06, ADR-35
"""

from typing import Literal

from meritum_core.checks.contracts import Stance
from pydantic import RootModel

from meritum_worker.observability.gates.models import Frozen, Label, Seconds

type InputClass = Literal["claim", "needs_clarification", "out_of_scope"]
"""What the input classifier decides before the main model (F-07)."""


class InputCase(Frozen):
    """An input with the class the classifier should give it.

    Attributes:
        id: Unique id.
        text: The question; no real personal data (AGENTS.md).
        expected: The expected class.

    Features:
        US-BEZ-01, US-OBS-04, US-SPR-06, F-07, F-27
    """

    id: Label
    text: str
    expected: InputClass


class InputCases(RootModel[tuple[InputCase, ...]]):
    """The input classifier case file.

    Features:
        US-BEZ-01, US-OBS-04, US-SPR-06, F-07, F-27
    """


class ClassCall(Frozen):
    """One input classifier call on one input case.

    Attributes:
        case_id: The input case.
        label: The class the classifier gave.
        seconds: Time of the call.

    Features:
        US-BEZ-01, US-OBS-04, US-SPR-06, F-07, F-27
    """

    case_id: Label
    label: InputClass
    seconds: Seconds


class ClassCalls(RootModel[tuple[ClassCall, ...]]):
    """A recorded input classifier run.

    Features:
        US-BEZ-01, US-OBS-04, US-SPR-06, F-07, F-27
    """


class StanceCall(Frozen):
    """The NLI stance of a cited fragment next to the model's and a person's.

    Attributes:
        claim: The claim.
        fragment: The cited fragment.
        nli: Stance from the NLI model.
        model: Stance from the stance assessment of the check.
        manual: Stance a person gave, for the manual sample only.
        seconds: Time of the NLI call.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-06, ADR-35
    """

    claim: str
    fragment: str
    nli: Stance
    model: Stance
    manual: Stance | None = None
    seconds: Seconds


class StanceCalls(RootModel[tuple[StanceCall, ...]]):
    """A recorded NLI run.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-06, ADR-35
    """
