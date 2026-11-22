"""Settings of the `check` workflow's own: the pinned corpus snapshot.

Features:
    US-SPR-04, F-12, ADR-19
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from meritum_worker.checks.constants import CORPUS_VERSION_ENV, NO_CORPUS_VERSION


class ResearchSettings(BaseSettings):
    """What the research agents search, read from ``MERITUM_CORPUS_VERSION``.

    Attributes:
        corpus_version: the snapshot checks search; NO_CORPUS_VERSION (default)
            skips search_corpus.

    Features:
        US-SPR-04, F-12, ADR-19
    """

    model_config = SettingsConfigDict(frozen=True)

    # shortcut: one snapshot pinned by env, upgrade to the newest hourly
    # snapshot once worker#17 lands.
    corpus_version: str = Field(
        default=NO_CORPUS_VERSION, min_length=1, validation_alias=CORPUS_VERSION_ENV
    )
