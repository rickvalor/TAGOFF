# SOP-004 — Pre-push / release checklist

Run through this before any `git push` to a public remote, and before
tagging a release.

- [ ] Full test suite green, every language, from a **clean** build
      (clear `target/`/`.egg-info`/caches first — see
      [SOP-003](SOP-003-renaming.md)'s point 6 for why this matters even
      with no rename involved).
- [ ] Every public-facing surface passes [SOP-001](SOP-001-public-facing-content.md)
      — read it aloud as a stranger, not just spell-checked.
- [ ] No secrets or credentials in any tracked file (`git diff` the
      actual staged content, not just the file list).
- [ ] `LICENSE` present and its copyright line matches the current
      project name.
- [ ] Name and version consistent across every manifest (`Cargo.toml`,
      both `pyproject.toml` files if there are more than one, `setup.py`,
      `action.yml`, `.pre-commit-hooks.yaml`).
- [ ] `git status` clean before and after `git add` — no build artifact
      (`build/`, `*.egg-info/`, a regenerated binary) about to be
      committed by accident, and nothing real left out.
- [ ] If anything was renamed or moved this session, its own checklist
      ([SOP-003](SOP-003-renaming.md)) was actually completed, not just
      started.
