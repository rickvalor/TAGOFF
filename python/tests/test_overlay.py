"""Feature 5: user config overlay -- extra tracking rules layered on top
of the shipped lists, from a user-chosen directory, without ever touching
the shipped data/ files.
"""
from pathlib import Path

from link_scrub.scrubber import TrackerLists, clean_url, read_overlay, user_config_dir


def test_user_config_dir_honors_env_override(monkeypatch):
    monkeypatch.setenv("LINK_SCRUB_CONFIG_DIR", "/tmp/custom_link_scrub_dir")
    assert user_config_dir() == Path("/tmp/custom_link_scrub_dir")


def test_read_overlay_missing_files_returns_empty_strings(tmp_path):
    params, domains = read_overlay(tmp_path)
    assert params == ""
    assert domains == ""


def test_read_overlay_reads_real_files(tmp_path):
    (tmp_path / "extra_params.txt").write_text("mytrack\n", encoding="utf-8")
    params, domains = read_overlay(tmp_path)
    assert params == "mytrack\n"
    assert domains == ""


def test_extend_from_lines_adds_rules_without_losing_existing_ones():
    lists = TrackerLists.from_lines("utm_*\nfbclid\n", "clickwrap.example\n")
    lists.extend_from_lines("mytrack\n", "mytracker.example\n")
    result = clean_url("https://example.com/a?utm_source=x&mytrack=1", lists)
    assert sorted(result.removed_params) == ["mytrack", "utm_source"]


def test_from_files_applies_overlay_end_to_end(tmp_path, monkeypatch):
    (tmp_path / "extra_params.txt").write_text("mytrack\n", encoding="utf-8")
    monkeypatch.setenv("LINK_SCRUB_CONFIG_DIR", str(tmp_path))
    lists = TrackerLists.from_files()
    result = clean_url("https://example.com/a?mytrack=1&id=2", lists)
    assert result.cleaned == "https://example.com/a?id=2"
    assert result.removed_params == ["mytrack"]


def test_from_files_can_skip_overlay(tmp_path, monkeypatch):
    (tmp_path / "extra_params.txt").write_text("mytrack\n", encoding="utf-8")
    monkeypatch.setenv("LINK_SCRUB_CONFIG_DIR", str(tmp_path))
    lists = TrackerLists.from_files(include_overlay=False)
    result = clean_url("https://example.com/a?mytrack=1&id=2", lists)
    assert result.removed_params == []
