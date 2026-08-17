"""Chunking + retrieval tests. No Claude calls."""
from core.context import chunk_text, load_context, retrieve


def test_no_headers_is_one_chunk():
    chunks = chunk_text("plain.md", "Just a paragraph of requirement text.\nSecond line.")
    assert len(chunks) == 1
    assert chunks[0].section_title is None
    assert chunks[0].source_file == "plain.md"


def test_h2_headers_split_into_sections():
    text = (
        "## Apply valid coupon\n\n"
        "A user enters a valid code and sees the discount applied.\n\n"
        "## Remove coupon\n\n"
        "A user can remove an applied coupon before payment.\n"
    )
    chunks = chunk_text("coupon.md", text)
    assert len(chunks) == 2
    assert chunks[0].section_title == "Apply valid coupon"
    assert "discount applied" in chunks[0].text
    assert chunks[1].section_title == "Remove coupon"
    assert "remove an applied coupon" in chunks[1].text


def test_empty_file_yields_no_chunks():
    assert chunk_text("empty.md", "   \n\n  ") == []


def test_preamble_before_first_header_kept_as_its_own_chunk():
    text = "Intro paragraph.\n\n## Section One\n\nBody one.\n"
    chunks = chunk_text("mixed.md", text)
    assert len(chunks) == 2
    assert chunks[0].section_title is None
    assert chunks[0].text == "Intro paragraph."
    assert chunks[1].section_title == "Section One"


def test_load_context_and_retrieve(tmp_path):
    (tmp_path / "coupon.md").write_text(
        "## Apply coupon\n\nApplying a valid coupon reduces the order total.\n"
    )
    (tmp_path / "checkout.md").write_text(
        "## Payment step\n\nThe user enters card details to complete checkout.\n"
    )
    retriever = load_context(tmp_path)
    results = retrieve(retriever, "coupon discount total", k=2)
    assert len(results) == 2
    assert results[0].source_file == "coupon.md"


def test_load_context_multiple_dirs(tmp_path):
    reqs = tmp_path / "requirements"
    ctx = tmp_path / "context"
    reqs.mkdir()
    ctx.mkdir()
    (reqs / "a.md").write_text("## Feature A\n\nDoes something with widgets.\n")
    (ctx / "b.md").write_text("## Background\n\nWidgets are small reusable parts.\n")
    retriever = load_context([reqs, ctx])
    results = retrieve(retriever, "widgets", k=2)
    sources = {r.source_file for r in results}
    assert sources == {"a.md", "b.md"}
