"""Errors of the corpus slice.

Features:
    US-KOR-08, F-11
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
