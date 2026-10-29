"""Optional: watch the clipboard and auto-replace tracking-laden URLs with
cleaned ones, in place, as soon as you copy them.

Opt-in only -- this never starts on its own; run it explicitly with
`python -m url_scrub.clipboard_watch`. Requires `pyperclip`
(`pip install pyperclip`); exits with a clear message rather than silently
doing nothing if it's missing.
"""
from __future__ import annotations

import sys
import time

from .scrubber import TrackerLists, clean_url

POLL_SECONDS = 1.0


def main() -> int:
    try:
        import pyperclip
    except ImportError:
        print(
            "pyperclip is not installed (`pip install pyperclip`); clipboard watching needs it.",
            file=sys.stderr,
        )
        return 1

    lists = TrackerLists.from_files()
    last_seen: str | None = None
    print("Watching clipboard for tracking-laden URLs. Ctrl+C to stop.")
    try:
        while True:
            try:
                text = pyperclip.paste()
            except pyperclip.PyperclipException as exc:
                # round 10 finding: a long-running watcher WILL eventually
                # hit a transient clipboard-access failure (another app
                # briefly holding the Windows clipboard lock is a known,
                # common case) -- that must not kill the whole process.
                # Skip this tick and retry on the next one.
                print(f"  clipboard access failed, retrying: {exc}", file=sys.stderr)
                time.sleep(POLL_SECONDS)
                continue

            if text != last_seen:
                last_seen = text
                stripped = text.strip()
                if stripped.startswith("http://") or stripped.startswith("https://"):
                    result = clean_url(stripped, lists)
                    if result.cleaned != stripped:
                        try:
                            pyperclip.copy(result.cleaned)
                        except pyperclip.PyperclipException as exc:
                            print(f"  could not write clipboard, will retry next change: {exc}", file=sys.stderr)
                            time.sleep(POLL_SECONDS)
                            continue
                        last_seen = result.cleaned
                        print(f"cleaned: {result.cleaned}")
                        if result.unwrapped_redirect:
                            print("  unwrapped a redirector")
                        if result.removed_params:
                            print(f"  removed: {', '.join(result.removed_params)}")
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
