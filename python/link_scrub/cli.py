"""CLI entry point: `python -m link_scrub [urls...]` (or the installed
`link-scrub` console script).

Reads stdin (one URL per line) if no URLs are given as arguments. Flag
surface is kept identical to rust_core's CLI (see main.rs) on purpose, so
switching between the two implementations is a drop-in swap.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from .scrubber import CleanResult, TrackerLists, clean_url


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="link-scrub",
        description="Strip tracking query params from URLs and unwrap known link-shim redirectors.",
    )
    ap.add_argument("urls", nargs="*", help="URLs to clean; reads stdin (one per line) if omitted")
    ap.add_argument("-v", "--verbose", action="store_true", help="print what was removed/unwrapped, to stderr")
    ap.add_argument("--json", action="store_true", help="emit one JSON object per line instead of plain text")
    ap.add_argument("--stats", action="store_true", help="print an aggregate summary to stderr after processing")
    ap.add_argument(
        "--check", action="store_true", help="exit 1 if any URL had tracking to remove (CI/pre-commit gate)"
    )
    ap.add_argument("--list-params", action="store_true", help="print the loaded tracking-param rules and exit")
    ap.add_argument(
        "--list-domains", action="store_true", help="print the loaded redirector-domain rules and exit"
    )
    ap.add_argument(
        "--diff", action="store_true", help="show '- original' / '+ cleaned' pairs instead of just the result"
    )
    ap.add_argument("--input", metavar="FILE", help="read URLs from this file (one per line) instead of stdin")
    ap.add_argument(
        "--output", metavar="FILE", help="write cleaned URLs to this file instead of stdout (atomic write)"
    )
    args = ap.parse_args(argv)

    lists = TrackerLists.from_files()

    if args.list_params:
        for line in lists.describe_params():
            print(line)
        return 0
    if args.list_domains:
        for line in lists.describe_domains():
            print(line)
        return 0

    if args.urls:
        sources: Iterable[str] = args.urls
    elif args.input:
        sources = Path(args.input).read_text(encoding="utf-8").splitlines()
    else:
        sources = (line.rstrip("\n") for line in sys.stdin)

    # Buffering is only needed for --output's atomic write; the default
    # stdout path stays streaming (prints as it goes), same as before this
    # feature was added -- large stdin batches shouldn't need to fit in
    # memory just because --output exists as an option.
    out_lines: list[str] | None = [] if args.output else None
    any_tracking_found = False
    total = 0
    total_removed = 0
    total_unwrapped = 0
    param_counts: Counter[str] = Counter()

    for url in sources:
        if not url.strip():
            continue
        result = clean_url(url, lists)
        total += 1
        if result.unwrapped_redirect:
            total_unwrapped += 1
        if result.removed_params or result.unwrapped_redirect:
            any_tracking_found = True
        for p in result.removed_params:
            total_removed += 1
            param_counts[p.lower()] += 1
        line = _format_result(result, args)
        if out_lines is not None:
            out_lines.append(line)
        else:
            print(line)

    if args.output:
        _atomic_write(Path(args.output), "\n".join(out_lines) + ("\n" if out_lines else ""))

    if args.stats:
        _print_stats(total, total_removed, total_unwrapped, param_counts)

    return 1 if (args.check and any_tracking_found) else 0


def _format_result(result: CleanResult, args: argparse.Namespace) -> str:
    if args.json:
        return json.dumps(
            {
                "original": result.original,
                "cleaned": result.cleaned,
                "unwrapped_redirect": result.unwrapped_redirect,
                "removed_params": result.removed_params,
            }
        )
    if args.diff:
        if result.cleaned == result.original:
            return f"  unchanged: {result.original}"
        return f"- {result.original}\n+ {result.cleaned}"
    if args.verbose:
        extra = []
        if result.unwrapped_redirect:
            extra.append(f"  unwrapped redirect: {result.original}")
        if result.removed_params:
            extra.append(f"  removed: {', '.join(result.removed_params)}")
        if extra:
            print("\n".join(extra), file=sys.stderr)
    return result.cleaned


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent) if path.parent != Path("") else ".", prefix=".link_scrub_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def _print_stats(total: int, total_removed: int, total_unwrapped: int, param_counts: Counter[str]) -> None:
    print("--- link_scrub stats ---", file=sys.stderr)
    print(f"URLs processed:        {total}", file=sys.stderr)
    print(f"Tracking params removed: {total_removed}", file=sys.stderr)
    print(f"Redirectors unwrapped: {total_unwrapped}", file=sys.stderr)
    if param_counts:
        print("Top removed params:", file=sys.stderr)
        for name, count in param_counts.most_common(10):
            print(f"  {name}: {count}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
