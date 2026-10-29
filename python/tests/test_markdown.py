"""Feature 9: Markdown link cleaner."""
from link_scrub.markdown import clean_markdown, main
from link_scrub.scrubber import TrackerLists

FIXTURE_PARAMS = "utm_*\nfbclid\n"


def _lists() -> TrackerLists:
    return TrackerLists.from_lines(FIXTURE_PARAMS, "")


SAMPLE_MD = """\
# Notes

See [the article](https://example.com/a?utm_source=x&id=1) for details,
or read it raw at <https://example.com/b?fbclid=z>.

Already clean: [other](https://example.com/c?id=2 "a title").

[ref link][1] and here's the definition:

[1]: https://example.com/d?utm_medium=social
"""


def test_cleans_all_three_link_forms_and_preserves_everything_else():
    cleaned, stats = clean_markdown(SAMPLE_MD, _lists())

    assert stats.total_urls == 4
    assert stats.changed_urls == 3

    assert "[the article](https://example.com/a?id=1)" in cleaned
    assert "<https://example.com/b>" in cleaned
    assert '[other](https://example.com/c?id=2 "a title")' in cleaned  # unchanged, title preserved
    assert "[1]: https://example.com/d" in cleaned

    # prose, headings, and link text are completely untouched
    assert "# Notes" in cleaned
    assert "See [the article](" in cleaned
    assert "for details," in cleaned
    assert "[ref link][1] and here's the definition:" in cleaned
    assert cleaned.count("\n") == SAMPLE_MD.count("\n")


def test_inline_link_without_title_still_works():
    md = "[x](https://example.com?utm_source=y)"
    cleaned, stats = clean_markdown(md, _lists())
    assert cleaned == "[x](https://example.com)"
    assert stats.changed_urls == 1


def test_cli_dry_run_then_write(tmp_path, capsys):
    path = tmp_path / "doc.md"
    path.write_text(SAMPLE_MD, encoding="utf-8")
    original = path.read_bytes()

    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "3 had tracking removed" in out
    assert path.read_bytes() == original  # dry run didn't touch it

    assert main([str(path), "--write"]) == 0
    capsys.readouterr()
    assert (tmp_path / "doc.md.bak").read_bytes() == original
    assert "utm_source" not in path.read_text(encoding="utf-8")

    leftovers = list(tmp_path.glob(".link_scrub_tmp_*"))
    assert leftovers == []
