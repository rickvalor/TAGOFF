"""Tracking-parameter stripper and redirect-unwrapper (pure Python).

Mirrors rust_core/src/lib.rs's logic exactly, against the same two data
files (data/tracking_params.txt, data/tracking_domains.txt) so both
implementations stay in lockstep -- edit the data files once, not twice.
Zero network calls: the redirector-unwrap step only ever reads the
destination back out of the wrapper's own query string.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

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
    ) -> "TrackerLists":
        params_path = params_path or (DATA_DIR / "tracking_params.txt")
        domains_path = domains_path or (DATA_DIR / "tracking_domains.txt")
        return cls.from_lines(
            params_path.read_text(encoding="utf-8"),
            domains_path.read_text(encoding="utf-8"),
        )

    @classmethod
    def from_lines(cls, params_text: str, domains_text: str) -> "TrackerLists":
        params: set[str] = set()
        prefixes: list[str] = []
        for raw in params_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if lower.endswith("*"):
                prefixes.append(lower[:-1])
            else:
                params.add(lower)

        domains: set[str] = set()
        suffixes: list[str] = []
        for raw in domains_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if lower.startswith("*."):
                suffixes.append(lower[2:])
            else:
                domains.add(lower)

        return cls(
            params=params,
            param_prefixes=prefixes,
            redirect_domains=domains,
            redirect_domain_suffixes=suffixes,
        )

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
    if fragment and lists.is_tracking_param(fragment.split("=", 1)[0]):
        fragment = ""

    query = "&".join(k if v is None else f"{k}={v}" for k, v in kept)
    cleaned = urlunsplit((parts.scheme, parts.netloc, parts.path, query, fragment))
    return CleanResult(original=url, cleaned=cleaned, unwrapped_redirect=unwrapped, removed_params=removed)
