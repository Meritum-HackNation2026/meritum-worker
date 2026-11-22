"""Parts of a golden set case: a cited source and a prompt-injection attempt.

Sources keep only the address and a short cited fragment, never the full text
(ADR-27). An attack names the clean case that labels it (ADR-23).

Features:
    US-OBS-04, F-27, ADR-23, ADR-25, ADR-27
"""

from typing import Annotated, Literal

from meritum_core.checks.contracts import Validity
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from meritum_worker.observability.constants import MAX_QUOTE_CHARS

type Text = Annotated[str, Field(min_length=3)]
"""Text of at least three characters."""
type CaseId = Annotated[str, Field(pattern=r"^[A-J]-[a-z0-9-]{1,60}$")]
"""Case id: the scenario letter, a dash and a slug."""


class CaseSource(BaseModel):
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

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: HttpUrl
    publisher: Text
    title: Text
    quote: Annotated[str, Field(min_length=2, max_length=MAX_QUOTE_CHARS)]
    validity: Validity | None = None


class Injection(BaseModel):
    """A prompt-injection attempt and the clean case that labels it (ADR-23).

    Attributes:
        place: In the user's text or on a source page the case points to.
        payload: The injected instruction, in Polish unless the attack mixes languages.
        clean_case: Id of the same case without the instruction.

    Features:
        US-OBS-04, US-BEZ-01, ADR-23
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    place: Literal["user_text", "source_page"]
    payload: Text
    clean_case: CaseId
