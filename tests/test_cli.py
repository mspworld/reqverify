"""Regression test for _select_target_text's default-section selection.

No Claude calls — this only exercises chunking + selection logic.
"""
from cli import _select_target_text


def test_default_selection_skips_a_preamble_and_returns_the_first_real_section(tmp_path):
    """Found by running the real pipeline against requirements/coupon.md and
    requirements/_redteam_injected.md: both start with an H1 title line
    before their first ## header, so chunk_file() prepends a preamble chunk.
    _select_target_text used to return chunks[0] unconditionally — the
    preamble, not the section — silently starving intent extraction down to
    just the title line on every file shaped like this.
    """
    f = tmp_path / "req.md"
    f.write_text(
        "# Some Title\n\n"
        "## Real Section\n\n"
        "This is the actual requirement text that matters.\n"
    )
    result = _select_target_text(str(f), None)
    assert "actual requirement text" in result
    assert result != "# Some Title"


def test_default_selection_with_no_preamble_is_unaffected(tmp_path):
    f = tmp_path / "req.md"
    f.write_text("## Real Section\n\nText here.\n")
    result = _select_target_text(str(f), None)
    assert "Text here." in result


def test_default_selection_with_no_sections_returns_whole_file(tmp_path):
    f = tmp_path / "req.md"
    f.write_text("Just a plain paragraph, no headers at all.\n")
    result = _select_target_text(str(f), None)
    assert "plain paragraph" in result
