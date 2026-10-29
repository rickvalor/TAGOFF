"""Tracking-parameter stripper and redirect-unwrapper (pure Python).

Mirrors rust_core/src/lib.rs's logic exactly, against the same two data
files (data/tracking_params.txt, data/tracking_domains.txt) so both
implementations stay in lockstep -- edit the data files once, not twice.
Zero network calls: the redirector-unwrap step only ever reads the
destination back out of the wrapper's own query string.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit


def user_config_dir() -> Path | None:
    """Feature 5: where a user's own overlay files
    (`extra_params.txt`/`extra_domains.txt`, same format as the shipped
    `data/` lists) live. `TAGOFF_CONFIG_DIR` overrides everything, for
    tests and for anyone who wants a non-default location; otherwise
    `%APPDATA%\\tagoff` on Windows or `~/.config/tagoff` elsewhere.
    Returns `None` only if neither the override nor the platform's home
    variable is set -- never raises, never touches the filesystem itself.
    """
    override = os.environ.get("TAGOFF_CONFIG_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        return Path(appdata) / "tagoff" if appdata else None
    home = os.environ.get("HOME")
    return Path(home) / ".config" / "tagoff" if home else None


def read_overlay(dir_: Path) -> tuple[str, str]:
    """Feature 5: read `extra_params.txt`/`extra_domains.txt` out of
    `dir_` if they exist (empty string for either that doesn't), for
    merging via `TrackerLists.extend_from_lines`. Missing files are not an
    error -- most users will never create an overlay at all.
    """
    params_path = dir_ / "extra_params.txt"
    domains_path = dir_ / "extra_domains.txt"
    params = params_path.read_text(encoding="utf-8") if params_path.exists() else ""
    domains = domains_path.read_text(encoding="utf-8") if domains_path.exists() else ""
    return params, domains

def _resolve_data_dir() -> Path:
    """Find the tracker-list data directory.

    Two cases, tried in order:
    1. Installed wheel: `setup.py`'s build step copies the canonical
       `data/*.txt` into `tagoff/data/` at build time, so a real,
       non-editable install is self-contained (round 16 fix -- the
       original design only worked for an editable install, since it
       always looked two levels up at the source tree).
    2. Editable/source-checkout install: read the canonical `data/`
       directory directly, two levels up, so edits to it apply
       immediately with no rebuild -- this is the actual single source
       of truth during development.
    """
    packaged = Path(__file__).resolve().parent / "data"
    if (packaged / "tracking_params.txt").exists():
        return packaged
    source_tree = Path(__file__).resolve().parents[2] / "data"
    if (source_tree / "tracking_params.txt").exists():
        return source_tree
    raise FileNotFoundError(
        "Could not find tracking_params.txt in either the packaged location "
        f"({packaged}) or the source-tree location ({source_tree})."
    )


DATA_DIR = _resolve_data_dir()

# Query-param names that, across known link-shim services, hold the real
# destination URL the shim is wrapping.
DEST_PARAM_NAMES = frozenset(
    {"url", "u", "dest", "destination", "target", "redirect", "r", "to", "link"}
)


@dataclass
class TrackerLists:
    params: set[str]
    param_prefixes: list[str]
    redirect_domains: set[str]
    redirect_domain_suffixes: list[str]

    @classmethod
    def from_files(
        cls,
        params_path: Path | None = None,
        domains_path: Path | None = None,
        include_overlay: bool = True,
    ) -> "TrackerLists":
        params_path = params_path or (DATA_DIR / "tracking_params.txt")
        domains_path = domains_path or (DATA_DIR / "tracking_domains.txt")
        lists = cls.from_lines(
            params_path.read_text(encoding="utf-8"),
            domains_path.read_text(encoding="utf-8"),
        )
        if include_overlay:
            dir_ = user_config_dir()
            if dir_ is not None:
                extra_params, extra_domains = read_overlay(dir_)
                lists.extend_from_lines(extra_params, extra_domains)
        return lists

    @classmethod
    def from_lines(cls, params_text: str, domains_text: str) -> "TrackerLists":
        lists = cls(params=set(), param_prefixes=[], redirect_domains=set(), redirect_domain_suffixes=[])
        lists.extend_from_lines(params_text, domains_text)
        return lists

    def extend_from_lines(self, params_text: str, domains_text: str) -> None:
        """Feature 5 (user config overlay): merge more rules into an
        existing `TrackerLists`, same text format as `from_lines`. Used to
        layer a user's own `extra_params.txt`/`extra_domains.txt` on top of
        the shipped lists without ever touching the shipped files.
        """
        for raw in params_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if lower.endswith("*"):
                self.param_prefixes.append(lower[:-1])
            else:
                self.params.add(lower)

        for raw in domains_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if lower.startswith("*."):
                self.redirect_domain_suffixes.append(lower[2:])
            else:
                self.redirect_domains.add(lower)

    def is_tracking_param(self, key: str) -> bool:
        lower = key.lower()
        if lower in self.params:
            return True
        return any(lower.startswith(p) for p in self.param_prefixes)

    def is_known_redirector(self, host: str) -> bool:
        lower = host.lower()
        if lower in self.redirect_domains:
            return True
        return any(lower == suf or lower.endswith(f".{suf}") for suf in self.redirect_domain_suffixes)

    def describe_params(self) -> list[str]:
        """Feature 3 (`--list-params`): human-readable lines describing
        every loaded param rule, sorted, so a user can audit exactly what
        will be stripped before trusting the tool with a real link.
        """
        lines = [f"exact : {p}" for p in sorted(self.params)]
        lines += [f"prefix: {p}*" for p in sorted(self.param_prefixes)]
        return lines

    def describe_domains(self) -> list[str]:
        """Feature 3 (`--list-domains`): same idea as `describe_params`,
        for the redirector-domain list.
        """
        lines = [f"exact : {d}" for d in sorted(self.redirect_domains)]
        lines += [f"suffix: *.{d}" for d in sorted(self.redirect_domain_suffixes)]
        return lines


def _parse_query_raw(query: str) -> list[tuple[str, str | None]]:
    """Split a raw query string into (key, value) pairs without decoding or
    re-encoding anything -- so a param we don't touch comes back out
    byte-identical to how it went in. Mirrors rust_core's `parse_query`.

    `value` is `None` when the pair had no `=` at all (e.g. `?flag`), and
    `""` when it had `=` with an empty value (`?flag=`) -- round 1's
    finding was that collapsing these two cases silently turned
    `?a=&b=1` into `?a&b=1`, violating the "byte-identical on anything
    untouched" guarantee the README promises.
    """
    if not query:
        return []
    pairs: list[tuple[str, str | None]] = []
    for part in query.split("&"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            pairs.append((k, v))
        else:
            pairs.append((part, None))
    return pairs


@dataclass
class CleanResult:
    original: str
    cleaned: str
    unwrapped_redirect: bool
    removed_params: list[str] = field(default_factory=list)


def clean_url(url: str, lists: TrackerLists, max_unwrap_depth: int = 3) -> CleanResult:
    """Clean one URL: try to unwrap a known link-shim redirector (up to
    `max_unwrap_depth` times, to handle a shim wrapping another shim), then
    strip every tracking query param and a purely-tracking fragment.

    Never raises. `urlsplit`/`urlunsplit` reject some malformed-but-real
    inputs outright (e.g. `ValueError: Invalid IPv6 URL` on an unbalanced
    `[`/`]` in the host) -- round 3's fuzz test found this. Anything that
    makes them raise is treated the same as "doesn't look like a URL":
    passed through unchanged, same as plain text would be.
    """
    try:
        return _clean_url_inner(url, lists, max_unwrap_depth)
    except ValueError:
        return CleanResult(original=url, cleaned=url, unwrapped_redirect=False, removed_params=[])


def _clean_url_inner(url: str, lists: TrackerLists, max_unwrap_depth: int) -> CleanResult:
    current = url.strip()
    unwrapped = False

    for _ in range(max_unwrap_depth):
        parts = urlsplit(current)
        host = parts.hostname or ""
        if not host or not lists.is_known_redirector(host):
            break
        pairs = _parse_query_raw(parts.query)
        dest_value = next((v for k, v in pairs if k.lower() in DEST_PARAM_NAMES), None)
        if not dest_value:
            break
        decoded = unquote(dest_value)
        if decoded.startswith("http://") or decoded.startswith("https://"):
            current = decoded
            unwrapped = True
        else:
            break

    parts = urlsplit(current)
    pairs = _parse_query_raw(parts.query)
    removed: list[str] = []
    kept: list[tuple[str, str | None]] = []
    for k, v in pairs:
        if lists.is_tracking_param(k):
            removed.append(k)
        else:
            kept.append((k, v))

    fragment = parts.fragment
    fragment_was_tracking = bool(fragment) and lists.is_tracking_param(fragment.split("=", 1)[0])
    if fragment_was_tracking:
        fragment = ""

    # Feature 7's idempotency fuzz test found this (and it's really a
    # second Law-2 violation, not just an idempotency bug): urlunsplit()
    # drops a bare trailing '?' or '#' whenever nothing follows it, even
    # when NOTHING was removed -- so "https://x.com/path?" silently became
    # "https://x.com/path" despite zero tracking params touched. Detect
    # whether the marker was actually present in the input and preserve a
    # bare one when nothing was removed from it.
    before_fragment = current.split("#", 1)[0]
    had_query_marker = "?" in before_fragment
    had_fragment_marker = "#" in current

    prefix = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    cleaned = prefix
    if kept:
        cleaned += "?" + "&".join(k if v is None else f"{k}={v}" for k, v in kept)
    elif had_query_marker and not removed:
        cleaned += "?"

    if fragment:
        cleaned += "#" + fragment
    elif had_fragment_marker and not fragment_was_tracking:
        cleaned += "#"

    return CleanResult(original=url, cleaned=cleaned, unwrapped_redirect=unwrapped, removed_params=removed)
