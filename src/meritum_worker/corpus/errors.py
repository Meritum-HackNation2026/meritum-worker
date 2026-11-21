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
