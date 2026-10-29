"""Features 1-4: --json, --stats, --check, --list-params/--list-domains,
exercised through the real CLI entry point (link_scrub.cli.main) so these
tests match what a user actually runs.
"""
import json

import pytest

from link_scrub.cli import main


def _run(capsys, argv):
    exit_code = main(argv)
    out, err = capsys.readouterr()
    return exit_code, out, err


def test_json_output(capsys):
    code, out, _ = _run(capsys, ["--json", "https://example.com/a?utm_source=x&id=1"])
    assert code == 0
    row = json.loads(out.strip())
    assert row["cleaned"] == "https://example.com/a?id=1"
    assert row["removed_params"] == ["utm_source"]
    assert row["unwrapped_redirect"] is False


def test_stats_summary(capsys):
    code, _, err = _run(
        capsys,
        [
            "--stats",
            "https://example.com/a?utm_source=x",
            "https://example.com/b?utm_source=y&fbclid=z",
        ],
    )
    assert code == 0
    assert "URLs processed:        2" in err
    assert "Tracking params removed: 3" in err
    assert "utm_source: 2" in err
    assert "fbclid: 1" in err


def test_check_flag_exits_nonzero_when_tracking_found(capsys):
    code, _, _ = _run(capsys, ["--check", "https://example.com/a?utm_source=x"])
    assert code == 1


def test_check_flag_exits_zero_when_clean(capsys):
    code, _, _ = _run(capsys, ["--check", "https://example.com/a?id=1"])
    assert code == 0


def test_list_params_includes_known_entries(capsys):
    code, out, _ = _run(capsys, ["--list-params"])
    assert code == 0
    assert "exact : fbclid" in out
    assert "prefix: utm_*" in out


def test_diff_mode_shows_minus_plus_for_changed_url(capsys):
    code, out, _ = _run(capsys, ["--diff", "https://example.com/a?utm_source=x"])
    assert code == 0
    assert "- https://example.com/a?utm_source=x" in out
    assert "+ https://example.com/a" in out


def test_diff_mode_shows_unchanged_for_clean_url(capsys):
    code, out, _ = _run(capsys, ["--diff", "https://example.com/a?id=1"])
    assert code == 0
    assert "unchanged: https://example.com/a?id=1" in out


def test_input_file_reads_urls_from_a_file(capsys, tmp_path):
    input_file = tmp_path / "urls.txt"
    input_file.write_text("https://example.com/a?utm_source=x\nhttps://example.com/b?id=1\n", encoding="utf-8")
    code, out, _ = _run(capsys, ["--input", str(input_file)])
    assert code == 0
    assert out.splitlines() == ["https://example.com/a", "https://example.com/b?id=1"]


def test_output_file_writes_atomically(capsys, tmp_path):
    output_file = tmp_path / "out.txt"
    code, out, _ = _run(capsys, ["--output", str(output_file), "https://example.com/a?utm_source=x"])
    assert code == 0
    assert out == ""  # nothing on stdout when --output is used
    assert output_file.read_text(encoding="utf-8") == "https://example.com/a\n"
    # no leftover temp file from the atomic-write dance
    leftovers = list(tmp_path.glob(".link_scrub_tmp_*"))
    assert leftovers == []


def test_list_domains_includes_known_entries(capsys):
    code, out, _ = _run(capsys, ["--list-domains"])
    assert code == 0
    assert "exact : l.facebook.com" in out
    assert "suffix: *.safelinks.protection.outlook.com" in out
