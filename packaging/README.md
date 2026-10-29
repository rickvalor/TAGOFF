# Packaging manifests, groundwork, not yet functional

Every file in this directory is a **template with placeholder values**,
not a working package manifest. None of them will install anything
correctly yet, because none of them can be made correct yet: all three
formats need a real download URL and a real SHA256 checksum of a built
release artifact, and **no GitHub Release exists for this project yet**.

What's missing before any of these can go live, per format:

- **Homebrew** (`homebrew/tagoff.rb`): needs a tagged GitHub release
  with a source tarball URL, and that tarball's real `sha256`. Computed
  via `shasum -a 256 <tarball>` once one exists.
- **Scoop** (`scoop/tagoff.json`): needs a released Windows binary
  (the Rust CLI, cross-compiled for `x86_64-pc-windows-gnu` or `-msvc` in
  CI, not yet set up; `.github/workflows/ci.yml` only builds and tests,
  it doesn't produce a release artifact) and that binary's real `hash`.
- **winget** (`winget/TAGOFF.yaml`): same binary requirement as Scoop,
  plus a Microsoft Store/winget-pkgs submission, which is a separate PR
  into `microsoft/winget-pkgs`, not something this repo controls alone.

**The next step, in order:** add a release workflow that builds and
uploads binaries for at least Windows/macOS/Linux, tag a real `v0.1.0`,
then come back to these three files and fill in the real URLs and
checksums the release produced. Only then are they true.
