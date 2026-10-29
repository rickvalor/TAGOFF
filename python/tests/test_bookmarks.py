"""Feature 8: browser bookmarks cleaner, against synthetic files shaped
exactly like real Chrome `Bookmarks` JSON and a real Netscape
Bookmarks.html export.
"""
import json

from tagoff.bookmarks import clean_chrome_bookmarks_json, clean_netscape_html, main
from tagoff.scrubber import TrackerLists

FIXTURE_PARAMS = "utm_*\nfbclid\n"
FIXTURE_DOMAINS = ""


def _lists() -> TrackerLists:
    return TrackerLists.from_lines(FIXTURE_PARAMS, FIXTURE_DOMAINS)


CHROME_BOOKMARKS = {
    "checksum": "abc123",
    "roots": {
        "bookmark_bar": {
            "type": "folder",
            "name": "Bookmark bar",
            "children": [
                {"type": "url", "name": "Example", "url": "https://example.com/a?utm_source=x&id=1"},
                {
                    "type": "folder",
                    "name": "Nested",
                    "children": [
                        {"type": "url", "name": "Deep", "url": "https://example.com/b?fbclid=z"},
                        {"type": "url", "name": "Clean", "url": "https://example.com/c?id=2"},
                    ],
                },
            ],
        },
        "other": {"type": "folder", "name": "Other bookmarks", "children": []},
    },
    "version": 1,
}

NETSCAPE_HTML = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><A HREF="https://example.com/a?utm_source=x&amp;id=1" ADD_DATE="123">Example</A>
    <DT><A HREF="https://example.com/c?id=2" ADD_DATE="456">Clean</A>
</DL><p>
"""


def test_chrome_bookmarks_cleans_nested_folders_without_mutating_input():
    original_url = CHROME_BOOKMARKS["roots"]["bookmark_bar"]["children"][0]["url"]
    cleaned, stats = clean_chrome_bookmarks_json(CHROME_BOOKMARKS, _lists())

    assert stats.total_urls == 3
    assert stats.changed_urls == 2
    bar = cleaned["roots"]["bookmark_bar"]["children"]
    assert bar[0]["url"] == "https://example.com/a?id=1"
    nested = bar[1]["children"]
    assert nested[0]["url"] == "https://example.com/b"
    assert nested[1]["url"] == "https://example.com/c?id=2"  # unchanged

    # input dict is not mutated
    assert CHROME_BOOKMARKS["roots"]["bookmark_bar"]["children"][0]["url"] == original_url


def test_netscape_html_cleans_hrefs_and_preserves_everything_else():
    cleaned, stats = clean_netscape_html(NETSCAPE_HTML, _lists())
    assert stats.total_urls == 2
    assert stats.changed_urls == 1
    assert 'HREF="https://example.com/a?id=1"' in cleaned
    assert 'HREF="https://example.com/c?id=2"' in cleaned
    # structure/attributes/whitespace around the hrefs is untouched
    assert 'ADD_DATE="123">Example</A>' in cleaned
    assert cleaned.count("\n") == NETSCAPE_HTML.count("\n")


def test_cli_dry_run_does_not_modify_the_file(tmp_path, capsys):
    path = tmp_path / "Bookmarks"
    path.write_text(json.dumps(CHROME_BOOKMARKS), encoding="utf-8")
    original_bytes = path.read_bytes()

    exit_code = main([str(path)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "2 had tracking removed" in out
    assert "dry run only" in out
    assert path.read_bytes() == original_bytes


def test_cli_write_makes_a_backup_and_updates_in_place(tmp_path, capsys):
    path = tmp_path / "Bookmarks"
    path.write_text(json.dumps(CHROME_BOOKMARKS), encoding="utf-8")

    exit_code = main([str(path), "--write"])
    capsys.readouterr()

    assert exit_code == 0
    backup = tmp_path / "Bookmarks.bak"
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8")) == CHROME_BOOKMARKS

    updated = json.loads(path.read_text(encoding="utf-8"))
    assert updated["roots"]["bookmark_bar"]["children"][0]["url"] == "https://example.com/a?id=1"

    # no leftover atomic-write temp file
    leftovers = list(tmp_path.glob(".tagoff_tmp_*"))
    assert leftovers == []


def test_cli_output_flag_writes_a_copy_leaves_original_untouched(tmp_path, capsys):
    path = tmp_path / "Bookmarks"
    path.write_text(json.dumps(CHROME_BOOKMARKS), encoding="utf-8")
    original_bytes = path.read_bytes()
    out_path = tmp_path / "cleaned_copy.json"

    exit_code = main([str(path), "--output", str(out_path)])
    capsys.readouterr()

    assert exit_code == 0
    assert path.read_bytes() == original_bytes
    cleaned = json.loads(out_path.read_text(encoding="utf-8"))
    assert cleaned["roots"]["bookmark_bar"]["children"][0]["url"] == "https://example.com/a?id=1"
