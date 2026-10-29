"""Feature 9: clean every link in a Markdown file.

Handles the three link forms Markdown actually has:
- inline: `[text](https://example.com?utm_source=x)`
- autolink: `<https://example.com?utm_source=x>`
- reference-style definition: `[label]: https://example.com?utm_source=x`

Regex-based, matching only the URL span so everything else in the file
(link text, code blocks, surrounding prose, indentation) is byte-for-byte
untouched. Does NOT walk into fenced code blocks specially -- a URL
inside a ``` code fence that happens to match one of the three forms
above gets cleaned too, same as prose; this is a known, documented
scope limit, not an oversight.
"""
from __future__ import annotations

import argparse
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .scrubber import TrackerLists, clean_url

_INLINE_LINK_RE = re.compile(r'\]\((\s*)(\S+?)(\s+"[^"]*")?(\s*)\)')
_AUTOLINK_RE = re.compile(r"<(https?://[^\s<>]+)>")
_REFERENCE_DEF_RE = re.compile(r"^(\s*\[[^\]]+\]:\s*)(\S+)", re.MULTILINE)


@dataclass
class CleanStats:
    total_urls: int = 0
    changed_urls: int = 0


def _clean_one(url: str, lists: TrackerLists, stats: CleanStats) -> str:
    stats.total_urls += 1
    result = clean_url(url, lists)
    if result.cleaned != url:
        stats.changed_urls += 1
    return result.cleaned


def clean_markdown(text: str, lists: TrackerLists) -> tuple[str, CleanStats]:
    stats = CleanStats()

    def inline_sub(m: re.Match) -> str:
        cleaned = _clean_one(m.group(2), lists, stats)
        title = m.group(3) or ""
        return f"]({m.group(1)}{cleaned}{title}{m.group(4)})"

    text = _INLINE_LINK_RE.sub(inline_sub, text)

    def autolink_sub(m: re.Match) -> str:
        return f"<{_clean_one(m.group(1), lists, stats)}>"

    text = _AUTOLINK_RE.sub(autolink_sub, text)

    def reference_sub(m: re.Match) -> str:
        return f"{m.group(1)}{_clean_one(m.group(2), lists, stats)}"

    text = _REFERENCE_DEF_RE.sub(reference_sub, text)

    return text, stats


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tagoff_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tagoff-md",
        description="Clean tracking params out of every link in a Markdown file.",
    )
    ap.add_argument("path", help="a .md file")
    ap.add_argument("--write", action="store_true", help="write changes in place (makes a .bak backup first)")
    ap.add_argument("--output", metavar="FILE", help="write the cleaned file here instead of in place")
    args = ap.parse_args(argv)

    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    lists = TrackerLists.from_files()

    new_text, stats = clean_markdown(text, lists)
    print(f"{stats.total_urls} links found, {stats.changed_urls} had tracking removed.")

    if args.output:
        _atomic_write(Path(args.output), new_text)
        print(f"wrote cleaned copy to {args.output}")
    elif args.write:
        if stats.changed_urls == 0:
            print("nothing to change, not writing.")
            return 0
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(text, encoding="utf-8")
        _atomic_write(path, new_text)
        print(f"backup saved to {backup_path}, {path} updated in place.")
    else:
        print("dry run only -- pass --write to update in place, or --output FILE to write a copy.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
