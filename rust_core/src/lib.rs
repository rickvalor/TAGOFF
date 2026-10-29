//! link_scrub: strip tracking query parameters from URLs, and unwrap known
//! "link-shim" redirectors (Facebook's l.php, Reddit's out.reddit.com,
//! Slack's slack-redir.net, Outlook Safe Links, ...) back to the real
//! destination they wrap.
//!
//! This is a narrow, hand-rolled URL splitter -- not a general-purpose URL
//! parser. It only implements exactly the operations this tool needs
//! (splitting off the query string and fragment, extracting the host,
//! reading/writing `key=value&key=value` pairs) so the crate can stay at
//! zero external dependencies. Everything here is pure string manipulation;
//! nothing makes a network call, including the redirector-unwrap step,
//! which only ever reads the destination back out of the wrapper's own
//! query string.

use std::collections::HashSet;

/// Query-param names that, across known link-shim services, hold the real
/// destination URL the shim is wrapping.
const DEST_PARAM_NAMES: &[&str] = &[
    "url", "u", "dest", "destination", "target", "redirect", "r", "to", "link",
];

/// The two tracker lists loaded from `data/tracking_params.txt` and
/// `data/tracking_domains.txt`. Build with [`TrackerLists::from_lines`].
#[derive(Debug, Clone)]
pub struct TrackerLists {
    params: HashSet<String>,
    param_prefixes: Vec<String>,
    redirect_domains: HashSet<String>,
    redirect_domain_suffixes: Vec<String>,
}

impl TrackerLists {
    /// Parse the two list files from their text content (see the comment
    /// header of each file in `data/` for the exact format).
    pub fn from_lines(params_text: &str, domains_text: &str) -> Self {
        let mut params = HashSet::new();
        let mut param_prefixes = Vec::new();
        for raw in params_text.lines() {
            let line = raw.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let lower = line.to_ascii_lowercase();
            if let Some(prefix) = lower.strip_suffix('*') {
                param_prefixes.push(prefix.to_string());
            } else {
                params.insert(lower);
            }
        }

        let mut redirect_domains = HashSet::new();
        let mut redirect_domain_suffixes = Vec::new();
        for raw in domains_text.lines() {
            let line = raw.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let lower = line.to_ascii_lowercase();
            if let Some(suffix) = lower.strip_prefix("*.") {
                redirect_domain_suffixes.push(suffix.to_string());
            } else {
                redirect_domains.insert(lower);
            }
        }

        TrackerLists {
            params,
            param_prefixes,
            redirect_domains,
            redirect_domain_suffixes,
        }
    }

    fn is_tracking_param(&self, key: &str) -> bool {
        let lower = key.to_ascii_lowercase();
        if self.params.contains(&lower) {
            return true;
        }
        self.param_prefixes.iter().any(|p| lower.starts_with(p.as_str()))
    }

    fn is_known_redirector(&self, host: &str) -> bool {
        let lower = host.to_ascii_lowercase();
        if self.redirect_domains.contains(&lower) {
            return true;
        }
        self.redirect_domain_suffixes
            .iter()
            .any(|suf| lower == *suf || lower.ends_with(&format!(".{suf}")))
    }
}

/// Split a URL into (before_query, query, fragment). `before_query` keeps
/// the scheme, host and path untouched.
fn split_url(url: &str) -> (&str, Option<&str>, Option<&str>) {
    let (rest, fragment) = match url.find('#') {
        Some(i) => (&url[..i], Some(&url[i + 1..])),
        None => (url, None),
    };
    let (prefix, query) = match rest.find('?') {
        Some(i) => (&rest[..i], Some(&rest[i + 1..])),
        None => (rest, None),
    };
    (prefix, query, fragment)
}

fn extract_host(prefix: &str) -> Option<&str> {
    let after_scheme = match prefix.find("://") {
        Some(i) => &prefix[i + 3..],
        None => prefix,
    };
    let end = after_scheme.find(['/', ':']).unwrap_or(after_scheme.len());
    let host = &after_scheme[..end];
    if host.is_empty() {
        None
    } else {
        Some(host)
    }
}

/// A query param's value: `None` means the pair had no `=` at all (e.g.
/// `?flag`), `Some("")` means it had `=` with an empty value (`?flag=`).
/// Collapsing these to one case was round-trip pass 1's finding -- it
/// silently turned `?a=&b=1` into `?a&b=1`, violating the "byte-identical
/// on anything untouched" guarantee the README promises.
fn parse_query(query: &str) -> Vec<(String, Option<String>)> {
    if query.is_empty() {
        return Vec::new();
    }
    query
        .split('&')
        .filter(|p| !p.is_empty())
        .map(|pair| match pair.find('=') {
            Some(i) => (pair[..i].to_string(), Some(pair[i + 1..].to_string())),
            None => (pair.to_string(), None),
        })
        .collect()
}

/// Minimal percent-decode: handles `%XX` triples and leaves everything else
/// (including `+`) alone. Only ever used to read a nested destination URL
/// out of a wrapper param, never for display-critical text.
fn percent_decode(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%' && i + 2 < bytes.len() {
            if let Ok(hex) = std::str::from_utf8(&bytes[i + 1..i + 3]) {
                if let Ok(byte) = u8::from_str_radix(hex, 16) {
                    out.push(byte);
                    i += 3;
                    continue;
                }
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// Result of cleaning one URL.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CleanResult {
    pub original: String,
    pub cleaned: String,
    pub unwrapped_redirect: bool,
    pub removed_params: Vec<String>,
}

/// Clean one URL: first try to unwrap it (up to `max_unwrap_depth` times, to
/// handle a shim wrapping another shim), then strip every tracking query
/// param and a purely-tracking fragment.
pub fn clean_url(url: &str, lists: &TrackerLists, max_unwrap_depth: u8) -> CleanResult {
    let mut current = url.trim().to_string();
    let mut unwrapped = false;

    for _ in 0..max_unwrap_depth {
        let (prefix, query, _fragment) = split_url(&current);
        let host = match extract_host(prefix) {
            Some(h) => h,
            None => break,
        };
        if !lists.is_known_redirector(host) {
            break;
        }
        let q = match query {
            Some(q) => q,
            None => break,
        };
        let pairs = parse_query(q);
        let dest = pairs
            .iter()
            .find(|(k, _)| DEST_PARAM_NAMES.contains(&k.to_ascii_lowercase().as_str()));
        match dest {
            Some((_, Some(v))) => {
                let decoded = percent_decode(v);
                if decoded.starts_with("http://") || decoded.starts_with("https://") {
                    current = decoded;
                    unwrapped = true;
                } else {
                    break;
                }
            }
            Some((_, None)) | None => break,
        }
    }

    let (prefix, query, fragment) = split_url(&current);
    let mut removed = Vec::new();
    let kept: Vec<(String, Option<String>)> = match query {
        Some(q) => parse_query(q)
            .into_iter()
            .filter(|(k, _)| {
                let tracking = lists.is_tracking_param(k);
                if tracking {
                    removed.push(k.clone());
                }
                !tracking
            })
            .collect(),
        None => Vec::new(),
    };

    let mut cleaned = prefix.to_string();
    if !kept.is_empty() {
        cleaned.push('?');
        let parts: Vec<String> = kept
            .iter()
            .map(|(k, v)| match v {
                Some(v) => format!("{k}={v}"),
                None => k.clone(),
            })
            .collect();
        cleaned.push_str(&parts.join("&"));
    }
    if let Some(frag) = fragment {
        let frag_key = frag.split('=').next().unwrap_or("");
        if !lists.is_tracking_param(frag_key) {
            cleaned.push('#');
            cleaned.push_str(frag);
        }
    }

    CleanResult {
        original: url.to_string(),
        cleaned,
        unwrapped_redirect: unwrapped,
        removed_params: removed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_lists() -> TrackerLists {
        TrackerLists::from_lines(
            "utm_*\nfbclid\ngclid\n",
            "clickwrap.example\n*.shim.example\n",
        )
    }

    #[test]
    fn strips_exact_and_prefix_params() {
        let url = "https://example.com/a?utm_source=x&utm_medium=y&fbclid=z&keep=1";
        let result = clean_url(url, &test_lists(), 3);
        assert_eq!(result.cleaned, "https://example.com/a?keep=1");
        let mut removed = result.removed_params.clone();
        removed.sort();
        assert_eq!(removed, vec!["fbclid", "utm_medium", "utm_source"]);
    }

    #[test]
    fn leaves_clean_url_untouched() {
        let url = "https://example.com/a?keep=1";
        let result = clean_url(url, &test_lists(), 3);
        assert_eq!(result.cleaned, url);
        assert!(result.removed_params.is_empty());
        assert!(!result.unwrapped_redirect);
    }

    #[test]
    fn unwraps_known_redirector() {
        let wrapped =
            "https://clickwrap.example/go?url=https%3A%2F%2Freal.example%2Fpath%3Futm_source%3Dnews&gclid=abc";
        let result = clean_url(wrapped, &test_lists(), 3);
        assert!(result.unwrapped_redirect);
        assert_eq!(result.cleaned, "https://real.example/path");
    }

    #[test]
    fn unwraps_suffix_matched_domain() {
        let wrapped = "https://tenant123.shim.example/go?u=https%3A%2F%2Freal.example%2F";
        let result = clean_url(wrapped, &test_lists(), 3);
        assert!(result.unwrapped_redirect);
        assert_eq!(result.cleaned, "https://real.example/");
    }

    #[test]
    fn does_not_unwrap_unknown_domain() {
        let url = "https://notwrapped.example/go?url=https://real.example/path";
        let result = clean_url(url, &test_lists(), 3);
        assert!(!result.unwrapped_redirect);
        assert_eq!(result.cleaned, url);
    }

    #[test]
    fn preserves_explicit_empty_value_params() {
        // round 1 finding: "a=" (explicit, empty value) must not collapse
        // to the flag form "a" (no '=' at all) -- they're different inputs.
        let url = "https://example.com/path?a=&b=1&flag";
        let result = clean_url(url, &test_lists(), 3);
        assert_eq!(result.cleaned, url);
    }

    /// Round 2: cross-implementation parity, checked mechanically against
    /// one shared file (`tests/golden_cases.txt` at the repo root) instead
    /// of trusting that this file and `python/tests/test_scrubber.py`
    /// stayed in sync by eye.
    #[test]
    fn golden_cases_match() {
        let raw = include_str!("../../tests/golden_cases.txt");
        let lists = test_lists();
        let mut checked = 0;
        for (lineno, raw_line) in raw.lines().enumerate() {
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let fields: Vec<&str> = line.split("|||").map(|f| f.trim()).collect();
            assert_eq!(fields.len(), 4, "malformed golden case at line {}: {}", lineno + 1, raw_line);
            let (input, expected_cleaned, expected_removed, expected_unwrapped) =
                (fields[0], fields[1], fields[2], fields[3]);

            let result = clean_url(input, &lists, 3);
            assert_eq!(result.cleaned, expected_cleaned, "cleaned mismatch for input: {input}");
            let expected_removed_vec: Vec<&str> = if expected_removed.is_empty() {
                Vec::new()
            } else {
                expected_removed.split(',').collect()
            };
            assert_eq!(
                result.removed_params, expected_removed_vec,
                "removed-params mismatch for input: {input}"
            );
            assert_eq!(
                result.unwrapped_redirect,
                expected_unwrapped == "true",
                "unwrapped-redirect mismatch for input: {input}"
            );
            checked += 1;
        }
        assert!(checked >= 10, "expected at least 10 golden cases, only found {checked}");
    }

    /// Round 3: robustness fuzz. Manually verified first (malformed `%`
    /// sequences, null bytes, a 2MB input, a 200k-param query, nested
    /// redirector wrapping, non-ASCII, an IPv6-literal host) against both
    /// implementations with no panics/exceptions in either -- genuine "no
    /// finding," but codified here as a permanent regression test (a tiny
    /// seeded xorshift, no `rand` dependency) instead of a one-off manual
    /// check that evaporates after this session.
    #[test]
    fn fuzz_never_panics_and_never_grows_output() {
        let lists = test_lists();
        let mut state: u64 = 0x2545_F491_4F6C_DD1D;
        let mut next_u64 = || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            state
        };
        let alphabet: &[u8] = b"abcXYZ019 ?&=#%./:[]\0\\'\"<>+";

        for _ in 0..2000 {
            let len = (next_u64() % 120) as usize;
            let bytes: Vec<u8> = (0..len).map(|_| alphabet[(next_u64() as usize) % alphabet.len()]).collect();
            let input = String::from_utf8_lossy(&bytes).into_owned();
            let result = clean_url(&input, &lists, 3);
            assert!(
                result.cleaned.len() <= input.len(),
                "cleaned grew longer than input: {input:?} -> {:?}",
                result.cleaned
            );
        }
    }

    #[test]
    fn real_data_files_parse() {
        let params = include_str!("../../data/tracking_params.txt");
        let domains = include_str!("../../data/tracking_domains.txt");
        let lists = TrackerLists::from_lines(params, domains);
        assert!(lists.param_prefixes.iter().any(|p| p == "utm_"));
        assert!(lists.params.contains("fbclid"));
        assert!(!lists.redirect_domains.is_empty() || !lists.redirect_domain_suffixes.is_empty());
    }
}
