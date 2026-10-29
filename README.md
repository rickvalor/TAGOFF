# LINK_SCRUB

[![CI](https://github.com/OWNER/LINK_SCRUB/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
_(badge above will resolve once this is pushed to a real GitHub remote —
see `.github/workflows/ci.yml` directly until then.)_

A URL tracking-parameter stripper and link-shim unwrapper. Paste it a link
full of `utm_*`/`fbclid`/`gclid`/etc. junk (or one that's been wrapped
through Facebook's `l.php`, Reddit's `out.reddit.com`, Slack's
`slack-redir.net`, or an Outlook Safe Link), get back the clean destination.
See [`docs/EXAMPLES.md`](docs/EXAMPLES.md) for real before/after pairs,
including an Amazon product link and a wrapped Facebook share.

Zero network calls, two independent implementations tested against one
shared set of golden cases to guarantee they agree
(see [`docs/CRITIQUE_LEDGER.md`](docs/CRITIQUE_LEDGER.md) for the 14-round
hardening pass this went through — real bugs found and fixed, not just a
changelog).

Two parallel implementations, kept in lockstep against one shared data
source:

```
rust_core/      zero-dependency Rust library + CLI binary (fast path, embeds
                the lists at compile time)
python/         pure-Python package (link_scrub) + CLI (easy to run anywhere,
                no build step)
data/           the one shared source of truth both sides load:
                  tracking_params.txt   -- tracking query-param names/prefixes
                  tracking_domains.txt  -- known link-shim redirector hosts
test_fixtures/  golden_cases.txt -- shared test vectors both languages' real
                test suites (rust_core/tests/, python/tests/) load; not a
                suite of its own
scripts/        bench.py -- cross-language benchmark
docs/           CRITIQUE_LEDGER.md, EXAMPLES.md, BENCHMARKS.md
```

## Laws (binding)

1. **Zero network calls.** Cleaning a URL is pure string manipulation —
   splitting on `?`/`#`/`&`/`=`, percent-decoding, and reading a destination
   back out of a wrapper's *own* query string. Nothing here ever makes an
   HTTP request to resolve, expand, or verify a link. A domain appearing in
   `tracking_domains.txt` is not "visited" to confirm anything.
2. **Non-destructive on anything not on the list.** Only query params that
   exactly match or prefix-match an entry in `tracking_params.txt` are
   removed; a redirector is only unwrapped if its host is explicitly listed
   in `tracking_domains.txt` *and* it's carrying the destination in one of
   its own named params (`url`/`u`/`dest`/`destination`/`target`/`redirect`/
   `r`/`to`/`link`). Everything else in the URL passes through byte-for-byte
   unchanged — both implementations have a test asserting this.
3. **One source of truth.** The tracking lists live only in `data/`. Rust
   embeds them at compile time (`include_str!`); Python reads them at
   runtime. Edit the `.txt` files, not the code, to add/remove an entry —
   then rebuild the Rust binary to pick it up.
4. **The clipboard watcher is opt-in, always.** `link_scrub.clipboard_watch`
   never starts itself; it's a separate command you run deliberately, and it
   only ever touches the clipboard while it's actively running in the
   foreground of that terminal.

## Rust: build & test

This machine's default MSVC toolchain fails to link when the project path
contains a space (`link.exe` chokes on it) — same issue `AUDIO_FORGE` hit.
Use the GNU toolchain instead (already installed):

```powershell
cd rust_core
cargo +stable-x86_64-pc-windows-gnu test
cargo +stable-x86_64-pc-windows-gnu build --release
.\target\release\link_scrub.exe -v "https://example.com/a?utm_source=x&id=1"
```

Reads URLs from argv, or one per line from stdin if none are given. `-v`
prints what was removed/unwrapped to stderr.

## Python: install & run

```powershell
cd python
pip install -e .
link-scrub -v "https://example.com/a?utm_source=x&id=1"

# optional: auto-clean whatever URL you copy, while this stays running
pip install -e ".[clipboard]"
link-scrub-watch
```

This is an editable install (`-e`) on purpose: the shipped `data/` lists
live one level above the Python package, not inside it, so a built/
published wheel would not carry them yet (tracked as a known gap).

Running the tests (also installs `pytest` via the `dev` extra):

```powershell
pip install -e ".[dev]"
python -m pytest tests/ -q
```

## Extending the lists

Add a line to `data/tracking_params.txt` (plain name, or `name*` for a
prefix match) or `data/tracking_domains.txt` (plain host, or `*.host` for
host + all subdomains). Both files are plain text with `#` comments — see
the header of each for the exact format, and the inline "KNOWN
FALSE-POSITIVE RISK" notes for entries that are a real tradeoff, not a free
win. Python picks up edits immediately; Rust needs a rebuild. Update
`test_fixtures/golden_cases.txt` too if the change affects one of its cases — both
languages' test suites load that one file, so it's the fastest way to prove
they still agree.

## Status

- Correctness: both implementations pass the same 14+ golden cases plus a
  2000-iteration seeded fuzz with zero crashes/exceptions (see the
  [critique ledger](docs/CRITIQUE_LEDGER.md)).
- Packaging: Python installs via `pip install -e .` with console commands;
  Rust via `cargo build --release`. Neither is published anywhere yet.
- Known gaps, not yet built: a PyO3/maturin binding (today the two
  implementations don't call each other — see
  [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md) for what that costs), a
  non-editable distributable Python wheel, a browser extension front-end.
- License: [MIT](LICENSE).
