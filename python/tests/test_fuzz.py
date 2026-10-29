"""Round 3 of the critique ledger: robustness fuzz.

Manually verified first against both implementations (malformed `%`
sequences, null bytes, a 2MB input, a 200k-param query, nested redirector
wrapping, non-ASCII, an IPv6-literal host) -- zero exceptions in either,
genuine "no finding." Codified here as a permanent regression test (stdlib
`random`, no `hypothesis` dependency) instead of a one-off manual check
that evaporates after this session.
"""
import random
import string

from url_scrub.scrubber import TrackerLists, clean_url

ALPHABET = "abcXYZ019 ?&=#%./:[]\0\\'\"<>+"


def test_fuzz_never_raises_and_never_grows_output():
    lists = TrackerLists.from_files()
    rng = random.Random(0xC0FFEE)
    for _ in range(2000):
        length = rng.randrange(0, 120)
        candidate = "".join(rng.choice(ALPHABET) for _ in range(length))
        result = clean_url(candidate, lists)
        assert len(result.cleaned) <= len(candidate), (
            f"cleaned grew longer than input: {candidate!r} -> {result.cleaned!r}"
        )


def test_fuzz_unicode_never_raises():
    lists = TrackerLists.from_files()
    rng = random.Random(0xBADC0DE)
    pool = string.ascii_letters + "?&=#%./:[]" + "é中文\U0001f600"
    for _ in range(500):
        length = rng.randrange(0, 80)
        candidate = "".join(rng.choice(pool) for _ in range(length))
        clean_url(candidate, lists)  # only asserting this doesn't raise
