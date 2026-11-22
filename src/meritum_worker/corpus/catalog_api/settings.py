"""Legal acts the ``api.sejm.gov.pl`` entry stores in full: ``MERITUM_CORPUS_LEGAL_*``.

Features:
    US-KOR-02, US-ZRD-05, F-10, F-12
"""

from typing import Annotated

from pydantic import Field, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

from meritum_worker.corpus.catalog_api.constants import (
    ELI_PATTERN,
    LEGAL_ACTS,
    LEGAL_ACTS_ENV_PREFIX,
    LEGAL_SEARCH_LIMIT,
)
from meritum_worker.corpus.documents import LegalActs

type Eli = Annotated[str, StringConstraints(pattern=ELI_PATTERN)]


class LegalActsSettings(BaseSettings):
    """The acts read with their full text, besides the year's titles.

    Attributes:
        acts: ELIs always read (``MERITUM_CORPUS_LEGAL_ACTS``, a JSON list);
            the constitution, consolidated main laws and minimum wage
            regulations by default.
        search_limit: Consolidated texts in force read from the ELI search,
            most recently changed first (``MERITUM_CORPUS_LEGAL_SEARCH_LIMIT``);
            0 reads none.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """

    model_config = SettingsConfigDict(env_prefix=LEGAL_ACTS_ENV_PREFIX, frozen=True)

    acts: tuple[Eli, ...] = LEGAL_ACTS
    search_limit: int = Field(default=LEGAL_SEARCH_LIMIT, ge=0, le=500)

    def legal_acts(self) -> LegalActs:
        """The acts as the ingestion's ports carry them.

        Returns:
            ``IngestDeps.legal``.
        """
        return LegalActs(acts=self.acts, search_limit=self.search_limit)
