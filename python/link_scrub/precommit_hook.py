"""Feature 12: a pre-commit (pre-commit.com) hook that fails if any file
being committed contains a URL with tracking params or a wrapped
link-shim redirector -- catches a tracking-laden link sneaking into docs,
READMEs, or changelogs before it ships.

Takes a list of file paths (how pre-commit invokes a hook: one argv per
changed file matching the hook's `files:` filter) and scans each for
`https?://\\S+` substrings with a plain regex -- deliberately simple, not
format-aware like the Markdown/bookmarks tools, since a pre-commit hook
needs to work across whatever file types a repo's `files:` filter lets
through, not just `.md`.
"""
from __future__ import annotations

import re
import sys

from .scrubber import TrackerLists, clean_url

_URL_RE = re.compile(r"https?://[^\s)>\]\"']+")


def scan_file(path: str, lists: TrackerLists) -> list[str]:
    """Return one human-readable finding line per URL-with-tracking found
    in `path`, empty if none. Never raises on a file it can't read as
    text (binary files that happen to match the hook's glob, etc.) --
    skips those silently rather than failing the whole commit on an
    unrelated file.
    """
    try:
        text = open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        return []

    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _URL_RE.finditer(line):
            url = m.group(0).rstrip(".,;:!?")
            result = clean_url(url, lists)
            if result.cleaned != url:
                findings.append(f"{path}:{lineno}: {url}\n           -> {result.cleaned}")
    return findings


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        return 0

    lists = TrackerLists.from_files()
    all_findings: list[str] = []
    for path in paths:
        all_findings.extend(scan_file(path, lists))

    if all_findings:
        print("link-scrub-precommit: tracking-laden URLs found:\n")
        for finding in all_findings:
            print(finding)
        print(f"\n{len(all_findings)} link(s) need cleaning. Run link-scrub -v on them, or edit by hand.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
