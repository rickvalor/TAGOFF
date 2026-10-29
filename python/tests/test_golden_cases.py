"""Round 2 of the critique ledger: cross-implementation parity, checked
mechanically against one shared file (test_fixtures/golden_cases.txt at
the repo root, renamed from tests/ in round 15 to stop it looking like a
third test suite) instead of trusting that this suite and
rust_core/src/lib.rs's golden_cases_match test stayed in sync by eye.
"""
from pathlib import Path

import pytest

from link_scrub.scrubber import TrackerLists, clean_url

GOLDEN_FILE = Path(__file__).resolve().parents[2] / "test_fixtures" / "golden_cases.txt"
FIXTURE_PARAMS = "utm_*\nfbclid\ngclid\n"
FIXTURE_DOMAINS = "clickwrap.example\n*.shim.example\n"


def _load_cases() -> list[tuple[str, str, str, bool]]:
    cases = []
    for lineno, raw_line in enumerate(GOLDEN_FILE.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [f.strip() for f in line.split("|||")]
        assert len(fields) == 4, f"malformed golden case at line {lineno}: {raw_line}"
        input_url, expected_cleaned, expected_removed, expected_unwrapped = fields
        cases.append((input_url, expected_cleaned, expected_removed, expected_unwrapped == "true"))
    return cases


CASES = _load_cases()


def test_golden_file_has_enough_cases():
    assert len(CASES) >= 10


@pytest.mark.parametrize("input_url,expected_cleaned,expected_removed,expected_unwrapped", CASES)
def test_golden_case(input_url, expected_cleaned, expected_removed, expected_unwrapped):
    lists = TrackerLists.from_lines(FIXTURE_PARAMS, FIXTURE_DOMAINS)
    result = clean_url(input_url, lists)
    assert result.cleaned == expected_cleaned
    expected_removed_list = expected_removed.split(",") if expected_removed else []
    assert result.removed_params == expected_removed_list
    assert result.unwrapped_redirect == expected_unwrapped
