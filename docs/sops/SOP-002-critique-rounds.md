# SOP-002 — Critique rounds

**Written after:** 19 rounds across two passes on this project, 10 real
bugs found this way, zero found by inspection alone.

## When a round is required

- After any batch of new code or a new feature, before calling it done.
- Before any public push (see [SOP-004](SOP-004-release-checklist.md)).
- Whenever a new, qualitatively different surface is added (a new file
  format support, a new install path, a new UI) — these tend to hide
  gaps the existing test suite was never built to catch.

## Procedure

1. **Pick one real, falsifiable target.** A specific function, flag,
   packaging path, or UI surface — not "review the code."
2. **State the concern before testing.** Write down what might be wrong
   and why, before running anything. This is what makes the result a
   finding instead of a retroactive justification.
3. **Actually run it.** Build the real artifact (a real wheel, a real
   install into a throwaway venv, a real HTTP serve, a real WASM call).
   Never conclude from reading code alone that something works.
4. **Record the result in `docs/CRITIQUE_LEDGER.md`,** win or lose: target,
   finding (or explicit "no finding" — that's a valid, loggable result),
   fix, and exactly how it was verified. A round that finds nothing but
   was genuinely checked is not wasted; a round that wasn't actually run
   doesn't count.
5. **Every real bug gets a permanent regression test,** not just a prose
   note. If the next round's fuzz/property test would have caught it,
   say so and make sure it's wired in going forward.
6. **Re-run the full suite (every language)** before starting the next
   round or closing out the pass.

## What counts as a finding

A reproducible difference between actual behavior and what was claimed
or expected, confirmed by running something real. "This could
theoretically fail on X" is a hypothesis to go test, not a finding yet.
"I read it and it looks right" is never a finding either way.
