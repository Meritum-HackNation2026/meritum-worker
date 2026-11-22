"""The extraction asks for a query naming the document that settles a fact."""

from meritum_worker.checks.models import ExtractedClaim
from meritum_worker.checks.prompts.constants import EXTRACTION_INSTRUCTIONS


def test_a_fact_may_carry_a_fourth_query_naming_the_settling_document() -> None:
    # worker#170 H1: the extra Polish query names the act or announcement.
    assert "names the primary document" in EXTRACTION_INSTRUCTIONS
    claim = ExtractedClaim(
        claim="Sejm liczy 460 posłów.",
        kind="fact",
        explanation="Twierdzenie o liczbie posłów.",
        search_queries=[
            "liczba posłów Sejm",
            "Sejm 460 posłów",
            "Poland Sejm 460 deputies",
            "Konstytucja RP art. 96 liczba posłów",
        ],
    )
    assert claim.web_queries[-1] == "Konstytucja RP art. 96 liczba posłów"
