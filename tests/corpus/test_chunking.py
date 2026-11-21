from meritum_worker import corpus
from meritum_worker.corpus.constants import CHUNK_MAX_CHARS


def test_short_text_is_one_passage() -> None:
    assert corpus.chunk_text("Komunikat RCB.\n\nUwaga na burze.") == [
        "Komunikat RCB.\n\nUwaga na burze."
    ]


def test_paragraphs_are_grouped_up_to_the_limit() -> None:
    paragraph = "słowo " * (CHUNK_MAX_CHARS // 12)
    chunks = corpus.chunk_text("\n\n".join([paragraph.strip()] * 5))
    assert len(chunks) > 1
    assert all(len(chunk) <= CHUNK_MAX_CHARS for chunk in chunks)


def test_long_paragraph_is_split_at_spaces_without_losing_words() -> None:
    text = " ".join(f"w{i}" for i in range(2000))
    chunks = corpus.chunk_text(text)
    assert all(len(chunk) <= CHUNK_MAX_CHARS for chunk in chunks)
    assert " ".join(chunks).split() == text.split()


def test_blank_text_has_no_passages() -> None:
    assert corpus.chunk_text(" \n\n \t") == []


def test_word_longer_than_the_limit_is_cut() -> None:
    chunks = corpus.chunk_text("x" * (CHUNK_MAX_CHARS * 2 + 5))
    assert [len(c) for c in chunks] == [CHUNK_MAX_CHARS, CHUNK_MAX_CHARS, 5]
