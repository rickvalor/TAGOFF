# Benchmarks

Last run: 2026-10-29, on the dev machine (Threadripper 2950X), release build.
This is a point-in-time number from one run on one machine, not a
guarantee — re-run `python scripts/bench.py` yourself before quoting it
anywhere that matters.

```
python scripts/bench.py 50000
```

| | time | throughput |
|---|---|---|
| Python (in-process library call) | 0.873s | 57,246 urls/sec |
| Rust (CLI, piped via stdin/stdout) | 0.283s | 176,611 urls/sec |

**Rust was ~3.1x faster on this run — but that number is honest, not
flattering.** The Rust figure includes process-spawn and OS-pipe overhead
(`subprocess.run([...], input=..., stdout=DEVNULL)` from Python), because
that's the only interface that currently exists between the two — there's
no PyO3/maturin binding yet (tracked as a known gap, not built). The Python
number pays none of that; it's a tight in-process loop.

What this means in practice:
- If you call the **Rust CLI once per URL** (e.g. shelling out from a
  script), process-spawn overhead dominates and you will NOT see 3x — you
  may see Rust come out *slower* per call for small batches, purely from
  fork/exec cost.
- If you pipe a **large batch through the Rust CLI in one process** (as
  this benchmark does), the 3x holds and should grow with batch size,
  since the fixed spawn cost amortizes.
- A real PyO3 binding (calling the Rust core as a native extension, no
  process boundary) would very likely show a much larger gap, since it
  would remove the spawn/pipe cost entirely. Not measured — don't quote a
  number for that until it's built.

Re-run and update this file by hand after any change to either
implementation's hot path; it is not auto-generated or auto-checked in CI.
