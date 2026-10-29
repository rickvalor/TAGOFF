"""Feature 12: pre-commit hook."""
from tagoff.precommit_hook import main, scan_file
from tagoff.scrubber import TrackerLists


def _lists() -> TrackerLists:
    return TrackerLists.from_lines("utm_*\nfbclid\n", "")


def test_scan_file_finds_tracking_url_with_line_number(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(
        "line one\nsee https://example.com/a?utm_source=x here\nline three\n", encoding="utf-8"
    )
    findings = scan_file(str(path), _lists())
    assert len(findings) == 1
    assert f"{path}:2:" in findings[0]
    assert "https://example.com/a?utm_source=x" in findings[0]
    assert "https://example.com/a" in findings[0]


def test_scan_file_clean_file_has_no_findings(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("see https://example.com/a?id=1 here\n", encoding="utf-8")
    assert scan_file(str(path), _lists()) == []


def test_scan_file_strips_trailing_punctuation_from_matched_url(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("Check out (https://example.com/a?utm_source=x).\n", encoding="utf-8")
    findings = scan_file(str(path), _lists())
    assert len(findings) == 1
    assert "https://example.com/a?utm_source=x" in findings[0]


def test_scan_file_skips_unreadable_binary_file_without_raising(tmp_path):
    path = tmp_path / "image.png"
    path.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10]))
    assert scan_file(str(path), _lists()) == []


def test_main_exits_nonzero_with_findings(tmp_path, capsys):
    path = tmp_path / "README.md"
    path.write_text("see https://example.com/a?utm_source=x here\n", encoding="utf-8")
    exit_code = main([str(path)])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "tracking-laden URLs found" in out
    assert "1 link(s) need cleaning" in out


def test_main_exits_zero_when_all_files_clean(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("see https://example.com/a?id=1 here\n", encoding="utf-8")
    assert main([str(path)]) == 0


def test_main_exits_zero_with_no_files():
    assert main([]) == 0
