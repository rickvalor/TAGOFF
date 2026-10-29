# tagoff

Strip tracking query params from URLs and unwrap known link-shim
redirectors. Zero network calls.

This is the Python half of [TAGOFF](../README.md) — see the repo root
README for the full picture (what it does, the Laws, the Rust half,
how the shared tracker lists work). This file exists only because
`setuptools` requires a package's `readme` to live inside the package
root it's building from, not a parent directory.

```powershell
pip install -e .
tagoff -v "https://example.com/a?utm_source=x&id=1"

pip install -e ".[clipboard]"
tagoff-watch
```
