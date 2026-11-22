"""In-memory run repository and case sets for tests and behave scenarios.

Features:
    US-OBS-06, F-28
"""

from ._runs import InMemoryCaseSets, InMemoryEvalRuns

__all__ = ["InMemoryCaseSets", "InMemoryEvalRuns"]
