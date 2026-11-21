"""Golden set cases: input, channel, expected outcome, scenario A-J, sources.

A case's verdict is the verdict of its main claim (US-OBS-04). Sources keep only
the address and a short cited fragment, never the full text (ADR-27). An attack
case points at the same case without the instruction, whose label it must share
(ADR-23).

Features:
    US-OBS-04, F-27, ADR-23, ADR-25, ADR-27
"""

from collections import Counter
from typing import Annotated, Literal, Self

from meritum_core.checks.contracts import Channel, CheckStatus, Validity, Verdict
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    RootModel,
    model_validator,
)

from meritum_worker.observability.constants import (
    MAX_QUOTE_CHARS,
    MAX_TEXT_CHARS,
    REPEAT_VARIANTS,
)

type Scenario = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
"""Scenario of the brief's sample questions, A-J."""
type Origin = Literal["organizer", "own"]
"""From the organiser's sample questions or written by us."""
type Variant = Literal[
    "same_session", "other_channel", "same_material", "other_material"
]
"""Repeat of another case (G, H) or same or other material (I)."""
type Fault = Literal["fact_check_api", "web_search", "llm"]
"""Provider failure forced in an evaluation run (scenario J)."""
type CaseId = Annotated[str, Field(pattern=r"^[A-J]-[a-z0-9-]{1,60}$")]
"""Case id: the scenario letter, a dash and a slug."""
type Text = Annotated[str, Field(min_length=3)]
"""Text of at least three characters."""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CaseSource(_Frozen):
    """A real, checkable source: its address and a short cited fragment.

    Attributes:
        url: Address of the source.
        publisher: Who published it.
        title: Title of the document.
        quote: Cited fragment, or a fact-checker's rating verbatim (ADR-34).
        validity: ``superseded`` when newer evidence replaced it (ADR-25).

    Features:
        US-OBS-04, F-27, ADR-25, ADR-27
    """

    url: HttpUrl
    publisher: Text
    title: Text
    quote: Annotated[str, Field(min_length=2, max_length=MAX_QUOTE_CHARS)]
    validity: Validity | None = None


class Injection(_Frozen):
    """A prompt-injection attempt and the clean case that labels it (ADR-23).

    Attributes:
        place: In the user's text or on a source page the case points to.
        payload: The injected instruction, in Polish unless the attack mixes languages.
        clean_case: Id of the same case without the instruction.

    Features:
        US-OBS-04, US-BEZ-01, ADR-23
    """

    place: Literal["user_text", "source_page"]
    payload: Text
    clean_case: CaseId


class GoldenCase(_Frozen):
    """One case of the golden set or of the jury's file.

    Attributes:
        id: Unique id, starting with the scenario letter.
        scenario: Scenario A-J of the brief.
        origin: From the organiser's sample questions or our own.
        channel: Channel the question comes through.
        text: Question as the user writes it.
        url: Link sent with the question.
        image_text: Text and date visible on the prepared screenshot (scenario F).
        session: Session label; repeats in one session share it (scenario H).
        main_claim: The claim whose verdict is the case's verdict.
        expected_status: Expected outcome state.
        expected_verdict: Expected verdict of the main claim when the state is done.
        expected_behavior: What the answer must say, in Polish.
        sources: Sources the answer should rely on.
        variant: Repeat of another case (G, H) or same or other material (I).
        related_case: The case a repeat repeats; only repeat variants have one.
        injection: The injected instruction, for attack cases.
        fault: Provider failure forced in the run (scenario J).

    Features:
        US-OBS-04, F-27
    """

    id: CaseId
    scenario: Scenario
    origin: Origin
    channel: Channel
    text: Annotated[str | None, Field(min_length=3, max_length=MAX_TEXT_CHARS)] = None
    url: HttpUrl | None = None
    image_text: Text | None = None
    session: Text | None = None
    main_claim: Text
    expected_status: CheckStatus
    expected_verdict: Verdict | None = None
    expected_behavior: Text
    sources: tuple[CaseSource, ...] = ()
    variant: Variant | None = None
    related_case: CaseId | None = None
    injection: Injection | None = None
    fault: Fault | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        has_input = any((self.text, self.url, self.image_text))
        is_done = self.expected_status == "done"
        is_failure = self.expected_status == "technical_failure"
        if not self.id.startswith(f"{self.scenario}-"):
            msg = "a case id starts with its scenario letter"
            raise ValueError(msg)
        if not has_input:
            msg = "a case needs text, a URL or a screenshot"
            raise ValueError(msg)
        if is_done != (self.expected_verdict is not None):
            msg = "a verdict is expected exactly when the state is done"
            raise ValueError(msg)
        if (self.fault is not None) != is_failure:
            msg = "a forced fault goes with technical_failure and only with it"
            raise ValueError(msg)
        if (self.variant in REPEAT_VARIANTS) != (self.related_case is not None):
            msg = "a repeat variant needs the related case and only it has one"
            raise ValueError(msg)
        return self


def _reference_problems(cases: dict[str, GoldenCase]) -> list[str]:
    problems: list[str] = []
    for case in cases.values():
        clean = case.injection.clean_case if case.injection else None
        refs = [ref for ref in (case.related_case, clean) if ref is not None]
        problems += [
            f"{case.id}: unknown case {ref}" for ref in refs if ref not in cases
        ]
    # Repeats run in file order, so the case they repeat must be asked first.
    order = {case_id: index for index, case_id in enumerate(cases)}
    problems += [
        f"{case.id}: must come after {case.related_case}"
        for case in cases.values()
        if order.get(case.related_case or "", -1) > order[case.id]
    ]
    return problems


def _attack_problems(cases: dict[str, GoldenCase]) -> list[str]:
    problems: list[str] = []
    for case in cases.values():
        clean = cases.get(case.injection.clean_case) if case.injection else None
        if not clean:
            continue
        if clean.injection is not None:
            problems.append(f"{case.id}: clean case {clean.id} is itself an attack")
            continue
        if case.main_claim != clean.main_claim:
            problems.append(f"{case.id}: main claim differs from clean case {clean.id}")
        label = (case.expected_status, case.expected_verdict)
        if label != (clean.expected_status, clean.expected_verdict):
            problems.append(f"{case.id}: label differs from clean case {clean.id}")
    return problems


def _variant_problems(cases: dict[str, GoldenCase]) -> list[str]:
    problems: list[str] = []
    for case in cases.values():
        first = cases.get(case.related_case or "")
        if not first:
            continue
        same_channel = case.channel == first.channel
        same_session = case.session is not None and case.session == first.session
        if case.variant == "same_session" and not (same_channel and same_session):
            problems.append(
                f"{case.id}: same_session needs the channel and session of {first.id}"
            )
        if case.variant == "other_channel" and same_channel:
            problems.append(
                f"{case.id}: other_channel needs a channel other than {first.id}"
            )
    return problems


class GoldenSet(RootModel[tuple[GoldenCase, ...]]):
    """A case file: unique ids, valid references, attack labels from clean cases.

    Attributes:
        root: The cases in file order.

    Features:
        US-OBS-04, F-27, ADR-23
    """

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        counts = Counter(case.id for case in self.root)
        duplicates = sorted(case_id for case_id, n in counts.items() if n > 1)
        if duplicates:
            msg = f"duplicate case ids: {', '.join(duplicates)}"
            raise ValueError(msg)
        cases = {case.id: case for case in self.root}
        problems = _reference_problems(cases) + _attack_problems(cases)
        problems += _variant_problems(cases)
        if problems:
            raise ValueError("; ".join(problems))
        return self
