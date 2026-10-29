"""CLI entry point: `python -m url_scrub [urls...]`.

Reads stdin (one URL per line) if no URLs are given as arguments.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable

from .scrubber import TrackerLists, clean_url


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="url-scrub",
        description="Strip tracking query params from URLs and unwrap known link-shim redirectors.",
    )
    ap.add_argument("urls", nargs="*", help="URLs to clean; reads stdin (one per line) if omitted")
    ap.add_argument("-v", "--verbose", action="store_true", help="print what was removed/unwrapped, to stderr")
    args = ap.parse_args(argv)

    lists = TrackerLists.from_files()
    sources: Iterable[str] = args.urls if args.urls else (line.rstrip("\n") for line in sys.stdin)

    for url in sources:
        if not url.strip():
            continue
        result = clean_url(url, lists)
        print(result.cleaned)
        if args.verbose:
            if result.unwrapped_redirect:
                print(f"  unwrapped redirect: {result.original}", file=sys.stderr)
            if result.removed_params:
                print(f"  removed: {', '.join(result.removed_params)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
