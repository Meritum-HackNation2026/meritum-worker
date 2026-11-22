import pytest

from meritum_worker.moderation.similarity import cosine, facts_agree


@pytest.mark.parametrize(
    ("first", "second", "agree"),
    [
        ("inflacja wynosi 5%", "inflacja wynosi 15%", False),
        ("inflacja wynosi 5%", "Inflacja to 5 %", True),
        ("Strajk 20 listopada", "Strajk 20 grudnia", False),
        ("Czy w Pcimiu zamkną szkołę?", "Czy Pcim zamyka szkołę?", True),
        ("Czy w Pcimiu zamkną szkołę?", "Czy w Krakowie zamkną szkołę?", False),
        ("Czy zamkną szkołę?", "Czy w Krakowie zamkną szkołę?", True),
    ],
)
def test_facts_must_agree(first: str, second: str, *, agree: bool) -> None:
    assert facts_agree(first, second) is agree


def test_cosine() -> None:
    assert cosine((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    assert cosine((0.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0)
