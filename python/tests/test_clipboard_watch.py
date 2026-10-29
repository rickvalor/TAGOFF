"""Round 10 of the critique ledger: the clipboard watcher must survive a
transient pyperclip failure (e.g. Windows briefly refusing to open the
clipboard because another app holds it) instead of letting it crash the
whole background process.
"""
import sys
import types

from url_scrub import clipboard_watch


class _FakePyperclipException(Exception):
    pass


def test_survives_transient_paste_failure(monkeypatch, capsys):
    calls = {"paste": 0}

    def fake_paste():
        calls["paste"] += 1
        if calls["paste"] == 1:
            raise _FakePyperclipException("could not open clipboard")
        # second tick: pretend the user then hits Ctrl+C, to end the test
        # cleanly once we've proven the first failure didn't kill the loop
        raise KeyboardInterrupt

    fake_module = types.SimpleNamespace(
        paste=fake_paste,
        copy=lambda _text: None,
        PyperclipException=_FakePyperclipException,
    )
    monkeypatch.setitem(sys.modules, "pyperclip", fake_module)
    monkeypatch.setattr(clipboard_watch.time, "sleep", lambda _seconds: None)

    exit_code = clipboard_watch.main()

    assert exit_code == 0
    assert calls["paste"] == 2
    err = capsys.readouterr().err
    assert "clipboard access failed, retrying" in err
