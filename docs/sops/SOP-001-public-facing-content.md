# SOP-001 — Public-facing content standards

**Written after:** the first version of `web_demo/` shipped with literal
`--` as a dash substitute throughout the visible copy, and a footer that
talked about the critique ledger and test suite instead of the product.
It read as AI-generated because, written carelessly, it was.

**Scope:** anything a stranger can land on with zero context — `web_demo/`,
the top of the root `README.md`, package descriptions in `pyproject.toml`/
`Cargo.toml`, the GitHub repo description, `action.yml`'s description
field. Internal docs (`docs/CRITIQUE_LEDGER.md`, code comments, commit
messages) are exempt — process detail belongs there, not here.

## Rules

1. **No literal `--` as a dash.** Use a period, a comma, or a real em
   dash (—) only where it's grammatically natural. If you typed `--` to
   mean "and here's the rest of the thought," rewrite the sentence.
2. **No internal process language.** Never mention round numbers, the
   critique ledger, test counts, fuzz iterations, or commit/PR history
   on a public-facing surface. A visitor trying the tool doesn't care how
   it was built, and a reviewer judging craft will find
   `docs/CRITIQUE_LEDGER.md` on their own — it doesn't need to leak into
   the product.
3. **No narrating the page at itself.** Don't describe what the page is
   doing ("this demo," "running in this tab") beyond facts the user
   actually needs (e.g., "runs on your device" is a real, relevant
   privacy claim; "live WASM demo" is implementation detail dressed as a
   feature).
4. **Follow the frontend-design anti-tell checklist** before shipping any
   new visual surface: no cream-background-plus-serif-plus-terracotta, no
   near-black-plus-acid-accent, no SaaS-card kit (identical rounded cards,
   soft grey shadow on everything), no ALL-CAPS eyebrow labels, no
   middle-dot-joined meta strings, no arrow (→) tacked onto button/link
   text, no generic system-font stack when the subject calls for something
   more deliberate.
5. **Read it aloud as a stranger before publishing.** If any sentence
   sounds like a developer's running commentary rather than finished
   product copy, rewrite it. This is the actual test — the rules above are
   just the specific failures that test already caught once.

## Enforcement

Part of the pre-push checklist, [SOP-004](SOP-004-release-checklist.md).
A violation found after the fact gets logged as a critique-round finding
([SOP-002](SOP-002-critique-rounds.md)), same as a code bug — "the copy
reads like AI slop" is a real, falsifiable finding, not a vibe.
