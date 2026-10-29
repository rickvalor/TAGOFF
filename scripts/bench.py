"""Benchmark: Rust CLI vs. Python library, cleaning the same batch of
synthetic tracking URLs. No external dependencies -- stdlib only.

    python scripts/bench.py [N]     # N URLs, default 50_000

Numbers are written to docs/BENCHMARKS.md by hand after a run (not
auto-appended) -- see that file's own note on why.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUST_BIN = ROOT / "rust_core" / "target" / "release" / "tagoff.exe"

sys.path.insert(0, str(ROOT / "python"))
from tagoff.scrubber import TrackerLists, clean_url  # noqa: E402


def make_urls(n: int) -> list[str]:
    urls = []
    for i in range(n):
        urls.append(
            f"https://example.com/article/{i}"
            f"?utm_source=newsletter&utm_medium=email&utm_campaign=w{i % 52}"
            f"&fbclid=abc{i}&id={i}"
        )
    return urls


def bench_python(urls: list[str]) -> float:
    lists = TrackerLists.from_files()
    start = time.perf_counter()
    for url in urls:
        clean_url(url, lists)
    return time.perf_counter() - start


def bench_rust(urls: list[str]) -> float:
    payload = "\n".join(urls) + "\n"
    start = time.perf_counter()
    subprocess.run(
        [str(RUST_BIN)],
        input=payload,
        stdout=subprocess.DEVNULL,
        text=True,
        check=True,
    )
    return time.perf_counter() - start


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
    if not RUST_BIN.exists():
        print(f"Rust release binary not found at {RUST_BIN}; build it first:")
        print("  cd rust_core && cargo +stable-x86_64-pc-windows-gnu build --release")
        return 1

    urls = make_urls(n)
    print(f"Cleaning {n:,} synthetic URLs...")

    py_seconds = bench_python(urls)
    print(f"  Python: {py_seconds:.3f}s  ({n / py_seconds:,.0f} urls/sec)")

    rust_seconds = bench_rust(urls)
    print(f"  Rust:   {rust_seconds:.3f}s  ({n / rust_seconds:,.0f} urls/sec)")

    print(f"  Rust is {py_seconds / rust_seconds:.1f}x faster on this run"
          f" (includes Rust's process-spawn + stdin-pipe overhead, which the"
          f" Python number does NOT pay -- see docs/BENCHMARKS.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
