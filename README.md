# tagoff

[![CI](https://github.com/rickvalor/TAGOFF/actions/workflows/ci.yml/badge.svg)](https://github.com/rickvalor/TAGOFF/actions/workflows/ci.yml)

Removes tracking parameters from URLs and unwraps link-shim redirectors
(Facebook's `l.php`, Reddit's `out.reddit.com`, Slack's `slack-redir.net`,
Outlook Safe Links). Paste in a link full of `utm_source`, `fbclid`,
`gclid`, and similar junk; get back the clean destination. Real
before/after examples, including a wrapped Facebook share and an Amazon
product link, are in [`docs/EXAMPLES.md`](docs/EXAMPLES.md).

Two independent implementations, Rust and Python, tested against one
shared set of cases to keep them in agreement. Zero network calls: both
only ever read and rewrite the URL string itself.

A live, in-browser version runs entirely on-device via WebAssembly. Build
it once (`web_demo/build.sh`), then serve `web_demo/` with any static
file server (e.g. `python -m http.server`) and open it locally.

Two parallel implementations, kept in lockstep against one shared data
source:

```
rust_core/      zero-dependency Rust library + CLI binary (fast path, embeds
                the lists at compile time)
python/         pure-Python package (tagoff) + CLI + extra tools
                (bookmarks cleaner, Markdown link cleaner, pre-commit hook)
wasm_demo/      raw-C-ABI WASM wrapper around rust_core (no wasm-bindgen,
                stays dependency-free); verify.mjs proves it end-to-end via Node
web_demo/       static, client-side browser demo; build.sh stages the wasm
                binary + data files, then it's just index.html + demo.js
data/           the one shared source of truth both Rust/Python sides load:
                  tracking_params.txt   tracking query-param names/prefixes
                  tracking_domains.txt  known link-shim redirector hosts
test_fixtures/  golden_cases.txt, shared test vectors both languages' real
                test suites (rust_core/tests/, python/tests/) load; not a
                suite of its own
completions/    bash/zsh/PowerShell shell completions
packaging/      Homebrew/Scoop/winget manifest templates, not yet
                functional; see packaging/README.md for why
scripts/        bench.py, the cross-language benchmark
docs/           CRITIQUE_LEDGER.md, EXAMPLES.md, BENCHMARKS.md
action.yml, .pre-commit-hooks.yaml, pyproject.toml/setup.py (root)
                let other repos consume this one as a CI Action or a
                pre-commit hook; see the "Features" section below
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
4. **The clipboard watcher is opt-in, always.** `tagoff.clipboard_watch`
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
.\target\release\tagoff.exe -v "https://example.com/a?utm_source=x&id=1"
```

Reads URLs from argv, or one per line from stdin if none are given. `-v`
prints what was removed/unwrapped to stderr.

## Python: install & run

```powershell
cd python
pip install -e .
tagoff -v "https://example.com/a?utm_source=x&id=1"

# optional: auto-clean whatever URL you copy, while this stays running
pip install -e ".[clipboard]"
tagoff-watch
```

`-e` is for development convenience (edits to `data/*.txt` apply without
reinstalling). A real, non-editable `pip install .`/wheel is also fully
self-contained (`setup.py` copies the lists in at build time). Extra
tools, same install:

```powershell
tagoff-bookmarks path/to/Bookmarks          # Chrome/Edge JSON, or a Netscape Bookmarks.html export
tagoff-md path/to/doc.md                    # cleans every link in a Markdown file
tagoff-precommit file1 file2 ...             # exits 1 if any file has a tracking-laden URL
```

All four of `--write`/`--output`/dry-run default/`--diff` behave the same
way across `tagoff`, `tagoff-bookmarks`, and `tagoff-md`:
dry-run by default, `--write` makes a `.bak` backup first.

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

## Features

The Rust and Python CLIs share the same flag surface: `-v/--verbose`,
`--json`, `--diff`, `--stats`, `--check` (exit 1 if anything had
tracking, for a CI/pre-commit gate), `--list-params`/`--list-domains`
(audit the rules before trusting them), `--input FILE`/`--output FILE`
(atomic write). A user config overlay
(`extra_params.txt`/`extra_domains.txt` in `%APPDATA%\tagoff` or
`~/.config/tagoff`, overridable via `TAGOFF_CONFIG_DIR`) lets you
add your own rules without touching the shipped lists. Shell completions
for bash/zsh/PowerShell are in `completions/`. Three more tools ship with
the Python package: a browser bookmarks cleaner, a Markdown link cleaner,
and a pre-commit-hook-compatible file scanner (also wired up as a GitHub
Action in `action.yml`) — see "Python: install & run" above.

## Status

- Correctness: both implementations pass the same golden cases plus a
  2000-iteration seeded fuzz with zero crashes/exceptions, including an
  idempotency guarantee (`clean(clean(x)) == clean(x)`) tested the same
  way (see the [critique ledger](docs/CRITIQUE_LEDGER.md) — 19 rounds, 10
  real bugs found and fixed across two passes).
- Packaging: Python installs via `pip install -e .` (dev) or `pip install .`
  (real, self-contained wheel) with 5 console commands; Rust via
  `cargo build --release`. A root-level `pyproject.toml`/`setup.py`
  (distinct from `python/`'s) makes `pip install .` work from the repo
  root too, which `.pre-commit-hooks.yaml` and `action.yml` both need.
  Nothing is published to PyPI/crates.io/a package manager yet.
- A static, zero-network browser demo of the Rust core (compiled to WASM,
  no `wasm-bindgen`) lives in `web_demo/`, verified end-to-end via Node
  before being wired into the actual page.
- Known gaps, not yet built: a PyO3/maturin binding (today the two
  implementations don't call each other — see
  [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md) for what that costs), a
  browser extension (the WASM demo is a static page, not an extension
  that intercepts clicks), real binary releases (so the `packaging/`
  manifests can go from templates to working).
- License: [MIT](LICENSE).
