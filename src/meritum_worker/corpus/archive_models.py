"""Models of the page archive: a request, a stored copy and the outcome.

Features:
    US-KOR-07, F-38
"""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict


class ArchiveRefusal(StrEnum):
    """Why no copy was made.

    Features:
        US-KOR-07, F-38
    """

    LOGIN_WALL = "login_wall"
    ROBOTS_OR_TDM = "robots_or_tdm"
    FETCH_FAILED = "fetch_failed"
    RATE_LIMITED = "rate_limited"


class ArchiveRequest(BaseModel, frozen=True):
    """A citizen's request to archive one public page.

    Attributes:
        url: the page; the page fetcher rejects anything but public http(s).
        owner_id: who asked; only they and moderators may read the copy.

    Features:
        US-KOR-07, F-38
    """

    url: str
    owner_id: str


class ArchiveCopy(BaseModel):
    """A stored copy with the terms it was made under.

    Attributes:
        archive_id: the id of the copy (the blob id of its text).
        blob_id: where the text is stored.
        url: the final URL of the page, after redirects.
        owner_id: who asked.
        sha256: hash of the stored bytes.
        archived_at: when the copy was made.
        expires_at: when retention deletes it at the latest.
        legal_basis: why we may keep it.
        access_rule: who may see it.
        deletion_procedure: how it is removed.

    Features:
        US-KOR-07, F-38
    """

    model_config = ConfigDict(frozen=True)

    archive_id: str
    blob_id: str
    url: str
    owner_id: str
    sha256: str
    archived_at: AwareDatetime
    expires_at: AwareDatetime
    legal_basis: str
    access_rule: str
    deletion_procedure: str


class ArchiveOutcome(BaseModel, frozen=True):
    """The result of an archiving request: a copy, or a refusal with a message.

    Attributes:
        archive: the stored copy; None when refused.
        refusal: why there is no copy.
        message: what the citizen is told when refused.

    Features:
        US-KOR-07, F-38
    """

    archive: ArchiveCopy | None = None
    refusal: ArchiveRefusal | None = None
    message: str | None = None
