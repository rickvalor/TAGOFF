"""Feature 8: clean every bookmark URL in a real browser export file.

Two formats, auto-detected:
- Chrome/Edge's native `Bookmarks` file (JSON, no extension) -- walks the
  `roots` tree recursively.
- The universal Netscape "Bookmarks.html" export (Firefox/Chrome/Safari
  all produce this via "Export Bookmarks...") -- finds every `href="..."`
  by exact span, not by re-serializing the HTML through a parser, so
  nothing else in the file's formatting changes.

Pure local file processing, zero network calls, same as everything else in
this project. Dry-run by default; `--write` makes a `.bak` backup first,
then writes atomically.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .scrubber import TrackerLists, clean_url


@dataclass
class CleanStats:
    total_urls: int = 0
    changed_urls: int = 0


def _clean_chrome_node(node: dict, lists: TrackerLists, stats: CleanStats) -> None:
    if node.get("type") == "url" and isinstance(node.get("url"), str):
        stats.total_urls += 1
        result = clean_url(node["url"], lists)
        if result.cleaned != node["url"]:
            stats.changed_urls += 1
            node["url"] = result.cleaned
    for child in node.get("children", []):
        if isinstance(child, dict):
            _clean_chrome_node(child, lists, stats)


def clean_chrome_bookmarks_json(data: dict, lists: TrackerLists) -> tuple[dict, CleanStats]:
    """`data` is the parsed content of a Chrome/Edge `Bookmarks` file.
    Returns a NEW dict (does not mutate the input) plus stats.
    """
    data = json.loads(json.dumps(data))  # deep copy without a dependency
    stats = CleanStats()
    for root in data.get("roots", {}).values():
        if isinstance(root, dict):
            _clean_chrome_node(root, lists, stats)
    return data, stats


_HREF_RE = re.compile(r'(?i)href\s*=\s*"([^"]*)"')


def clean_netscape_html(html_text: str, lists: TrackerLists) -> tuple[str, CleanStats]:
    """Clean every `href="..."` in a Netscape-format bookmarks export,
    replacing only the matched spans so everything else in the file
    (indentation, other attributes, folder structure) is untouched.

    Real exports HTML-escape `&` as `&amp;` inside the attribute value
    (found by the test fixture modeling a real export) -- without
    unescaping first, `...?utm_source=x&amp;id=1` splits on the literal
    `&` into params "utm_source=x" and "amp;id=1", so "id" is never
    recognized as its own param at all. Decode before cleaning, re-encode
    only the `&` back afterward (the one entity our own output could
    reintroduce; nothing else in a URL needs HTML-escaping inside an
    already-double-quoted attribute).
    """
    stats = CleanStats()
    out = []
    last_end = 0
    for m in _HREF_RE.finditer(html_text):
        stats.total_urls += 1
        original = m.group(1)
        decoded = html.unescape(original)
        result = clean_url(decoded, lists)
        reencoded = result.cleaned.replace("&", "&amp;")
        out.append(html_text[last_end : m.start(1)])
        out.append(reencoded)
        if reencoded != original:
            stats.changed_urls += 1
        last_end = m.end(1)
    out.append(html_text[last_end:])
    return "".join(out), stats


def _looks_like_json(text: str) -> bool:
    return text.lstrip().startswith("{")


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".link_scrub_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="link-scrub-bookmarks",
        description="Clean tracking params out of every URL in a browser bookmarks export.",
    )
    ap.add_argument("path", help="Chrome/Edge 'Bookmarks' JSON file, or a Netscape Bookmarks.html export")
    ap.add_argument("--write", action="store_true", help="write changes in place (makes a .bak backup first)")
    ap.add_argument("--output", metavar="FILE", help="write the cleaned file here instead of in place")
    args = ap.parse_args(argv)

    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    lists = TrackerLists.from_files()

    if _looks_like_json(text):
        data, stats = clean_chrome_bookmarks_json(json.loads(text), lists)
        new_text = json.dumps(data, indent=3)
    else:
        new_text, stats = clean_netscape_html(text, lists)

    print(f"{stats.total_urls} bookmark URLs found, {stats.changed_urls} had tracking removed.")

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
