"""Errors of the corpus slice.

Features:
    US-KOR-08, US-KOR-03, F-11, F-13
"""


class EuvsDisinfoUnavailableError(Exception):
    """The EUvsDisinfo MCP server failed or answered something unreadable.

    Features:
        US-KOR-08, F-11
    """


class MissingTokenError(Exception):
    """No EUvsDisinfo token in the environment; readiness reports it.

    Features:
        US-KOR-08, F-11
    """


class FactCheckUnavailableError(Exception):
    """Fact Check Tools API failed, hit its quota, refused the key or has no key.

    Its text never holds the API's own message or the key.

    Features:
        US-KOR-01, US-BEZ-03, F-14, F-18, ADR-34
    """


class FeedUnreadableError(Exception):
    """A feed or sitemap is not well-formed, safe XML of a known kind.

    Features:
        US-KOR-03, F-13
    """


class DiscoveryError(Exception):
    """An entry's feed or sitemap could not be read; its pages wait a run.

    Args:
        url: The feed or sitemap.
        reason: A ``FetchFailureReason`` code or ``feed_unreadable``.

    Attributes:
        url: The feed or sitemap.
        reason: Why it failed.

    Features:
        US-KOR-03, F-13
    """

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"{url}: {reason}")
        self.url = url
        self.reason = reason


class ArchiveAccessDeniedError(Exception):
    """No such archived copy, or the person may not read or delete it.

    Both cases look the same, so a stranger learns nothing about other copies.

    Features:
        US-KOR-07, F-38
    """
