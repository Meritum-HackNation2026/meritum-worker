"""Then-steps of features/evidence.feature: what the checked claim shows."""

from behave import then
from behave.runner import Context
from evidence_steps import NO_CHANGE
from meritum_core.checks.contracts import ClaimResult


def _claim(context: Context) -> ClaimResult:
    claim = context.claim
    assert isinstance(claim, ClaimResult)
    return claim


@then("fragment nie trafia do odpowiedzi")
def fragment_dropped(context: Context) -> None:
    assert context.state.citations == []
    assert _claim(context).citations == []


@then('twierdzenie bez cytatu dostaje werdykt "{verdict}" z opisem braków i bez siły')
def verdict_with_gaps(context: Context, verdict: str) -> None:
    claim = _claim(context)
    assert (claim.verdict, claim.strength) == (verdict, None)
    assert claim.unresolved is not None


@then('wynik nie jest "{verdict}" z powodu sprzecznych źródeł')
def not_conflicting(context: Context, verdict: str) -> None:
    claim = _claim(context)
    assert claim.verdict != verdict
    assert claim.strength is not None
    assert claim.strength.premises.agreement == "consistent"


@then(
    "wyjaśnienie mówi, że jedna liczba to szacunek z wypowiedzi, a druga konkretna"
    " pozycja i rok"
)
def explanation_names_measures(context: Context) -> None:
    explanation = _claim(context).explanation
    assert "szacunek" in explanation
    assert "pozycja budżetu za 2023" in explanation


@then(
    'werdykt to "{verdict}", a unresolved nazywa komunikat lokalnego organizatora'
    " transportu"
)
def unresolved_names_source(context: Context, verdict: str) -> None:
    claim = _claim(context)
    assert claim.verdict == verdict
    assert "organizatora transportu" in (claim.unresolved or "")


@then("odpowiedź mówi, że brak wyniku w bazie nie oznacza, że zmiany nie było")
def says_no_result_is_not_no_change(context: Context) -> None:
    assert NO_CHANGE in (_claim(context).unresolved or "")


@then('werdykt to "{verdict}", a unresolved mówi, że nie wiadomo, czy strajk się odbył')
def strike_unknown(context: Context, verdict: str) -> None:
    claim = _claim(context)
    assert claim.verdict == verdict
    assert "czy strajk się odbył" in (claim.unresolved or "")


@then("zapowiedź nie jest potwierdzeniem, że wydarzenie się odbyło")
def announcement_is_context(context: Context) -> None:
    # The announcement stays context; the contract shows no citation with an
    # unsettled, non-conflicting verdict.
    assert [c.citation.stance for c in context.state.citations] == ["context"]
    assert _claim(context).strength is None


@then('werdykt to "{verdict}" bez siły')
def verdict_without_strength(context: Context, verdict: str) -> None:
    claim = _claim(context)
    assert (claim.verdict, claim.strength) == (verdict, None)


@then("wynik ma cytaty obu stron")
def both_sides(context: Context) -> None:
    assert {c.stance for c in _claim(context).citations} == {"supports", "refutes"}


@then("starszy dowód ma validity superseded i nie liczy się do siły ani rozbieżności")
def older_superseded(context: Context) -> None:
    claim = _claim(context)
    validity = {c.source.id: c.validity for c in claim.citations}
    assert validity["gus-old"] == "superseded"
    assert claim.strength is not None
    assert claim.strength.premises.agreement == "consistent"


@then('werdykt to "{verdict}" z techniką outdated')
def outdated(context: Context, verdict: str) -> None:
    claim = _claim(context)
    assert (claim.verdict, claim.technique) == (verdict, "outdated")
