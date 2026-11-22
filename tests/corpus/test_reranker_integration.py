"""The configured reranker against the real provider: local only (-m integration).

Set ``MERITUM_RERANKER`` and ``MERITUM_RERANKER_*`` as in the README; with no
provider set it skips.
"""

import asyncio

import pytest
from meritum_core.corpus.rerank.contract import reranker_contract_violations

from meritum_worker.corpus import RerankerProvider, RerankerSettings, build_reranker


@pytest.mark.integration
def test_real_reranker_meets_the_core_contract() -> None:
    settings = RerankerSettings()
    if settings.provider is RerankerProvider.NONE:
        pytest.skip("MERITUM_RERANKER is not set")
    assert asyncio.run(reranker_contract_violations(build_reranker(settings))) == []
