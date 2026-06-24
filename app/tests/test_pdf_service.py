from __future__ import annotations

from app.services.pdf_service import chunk_pages, sanitize_text


def test_sanitize_removes_nul_bytes():
    assert "\x00" not in sanitize_text("abc\x00def")
    assert sanitize_text("abc\x00def") == "abcdef"


def test_sanitize_dehyphenates_line_breaks():
    assert sanitize_text("agri-\nculture") == "agriculture"


def test_sanitize_collapses_whitespace():
    assert sanitize_text("a    b\t\tc") == "a b c"


def test_chunk_pages_basic_and_ordinals():
    pages = ["a" * 1000, "b" * 1000]
    chunks = chunk_pages(pages, size=400, overlap=40)
    assert chunks, "doit produire des chunks"
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    # couverture : tout le texte est représenté, pages bornées dans [1, 2]
    assert min(c.page_start for c in chunks) == 1
    assert max(c.page_end for c in chunks) == 2


def test_chunk_pages_maps_pages():
    pages = ["alpha", "beta", "gamma"]
    chunks = chunk_pages(pages, size=4, overlap=1)
    for c in chunks:
        assert 1 <= c.page_start <= c.page_end <= 3
        assert c.token_count >= 1


def test_chunk_pages_no_infinite_loop_when_overlap_ge_size():
    # overlap >= size : le garde-fou doit éviter la boucle infinie et terminer.
    chunks = chunk_pages(["x" * 500], size=100, overlap=100)
    assert chunks
    assert chunks[-1].char_end == 500


def test_chunk_pages_empty():
    assert chunk_pages([]) == []
    assert chunk_pages(["", "   "]) == []
