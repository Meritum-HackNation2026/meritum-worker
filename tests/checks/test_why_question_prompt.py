"""A why-question about a fact-checker's figure is not a claim to refute."""

from meritum_worker.checks.prompts.constants import (
    ANSWER_INSTRUCTIONS,
    EXTRACTION_INSTRUCTIONS,
)


def test_extraction_keeps_the_source_figure_out_of_the_claims() -> None:
    # Scenario C: "Dlaczego w analizie Demagoga jest 650 mln zł?"
    assert "Dlaczego w analizie Demagoga jest 650 mln zł?" in EXTRACTION_INSTRUCTIONS


def test_answer_explains_what_each_figure_measures() -> None:
    assert "asks why a source gives a different figure" in ANSWER_INSTRUCTIONS
