# SOP-003 — Renaming this project

**Written after:** the url_scrub → link_scrub rename (round 15) and the
link_scrub → tagoff rename that followed it, both done for real reasons
(a cross-ecosystem naming inconsistency, then a deliberate name search),
not guessed at.

## Trigger

A branding decision, a registry-availability conflict, or explicit
direction to rename.

## Procedure

1. **Generate real candidates tied to the subject matter.** Not generic
   synonyms — words that actually describe what the tool does, in the
   theme already established.
2. **Check real availability before getting attached to anything.**
   PyPI (`https://pypi.org/pypi/<name>/json`, 404 = free) and crates.io
   (`https://crates.io/api/v1/crates/<name>` **with a real `User-Agent`
   header** — it 403s without one, which looks like "taken" but isn't;
   that mistake happened once already). Check every ecosystem the project
   actually publishes to.
3. **If a thematic/numerology check is wanted, use the real Numeris
   engine** (`AGENT_HUB/tools/numeris_cli.py profile <word>`, run from
   `AGENT_HUB/`), not a guess at what numerology would say. Report the
   actual output, including candidates that don't hit whatever target
   was asked for — don't cherry-pick quietly.
4. **Get explicit confirmation of the final name before touching any
   file.** A rename this mechanical is expensive to redo.
5. **Rename paths first** (`git mv`, so git tracks it as a rename, not a
   delete+add), **then** do a global text replace for every casing
   variant actually in use (`snake_case`, `kebab-case`, `UPPER_CASE`,
   and any language-specific form like a crate or package name) across
   every tracked file. Verify with a repo-wide, case-sensitive grep for
   the old name afterward — zero hits, not "looks done."
6. **Rebuild from a clean build cache and re-run the full suite, every
   language.** A stale `target/`/`.egg-info`/cached binary can bake in
   the old name's absolute path and pass tests that are secretly stale.
7. **If the top-level directory itself is being renamed, do that last,**
   after everything above is committed — then rebuild and re-run the
   full suite again from the new path. A directory move can silently
   invalidate cached absolute paths even when the rename itself succeeds
   (confirmed: `cargo test` after a bare directory rename failed with a
   stale `CARGO_BIN_EXE_*` path until `target/` was cleared).
8. **Commit each logical phase separately** (path+text rename; any
   rebuild-only fixups; the directory move) rather than one giant commit
   — makes it possible to tell "the rename" from "a bug the rename
   exposed" later.
