from link_scrub.scrubber import TrackerLists, clean_url

FIXTURE_PARAMS = "utm_*\nfbclid\ngclid\n"
FIXTURE_DOMAINS = "clickwrap.example\n*.shim.example\n"


def _lists() -> TrackerLists:
    return TrackerLists.from_lines(FIXTURE_PARAMS, FIXTURE_DOMAINS)


def test_strips_exact_and_prefix_params():
    url = "https://example.com/a?utm_source=x&utm_medium=y&fbclid=z&keep=1"
    result = clean_url(url, _lists())
    assert result.cleaned == "https://example.com/a?keep=1"
    assert set(result.removed_params) == {"utm_source", "utm_medium", "fbclid"}


def test_leaves_clean_url_untouched():
    url = "https://example.com/a?keep=1"
    result = clean_url(url, _lists())
    assert result.cleaned == url
    assert result.removed_params == []
    assert result.unwrapped_redirect is False


def test_unwraps_known_redirector():
    wrapped = (
        "https://clickwrap.example/go?url=https%3A%2F%2Freal.example%2Fpath"
        "%3Futm_source%3Dnews&gclid=abc"
    )
    result = clean_url(wrapped, _lists())
    assert result.unwrapped_redirect is True
    assert result.cleaned == "https://real.example/path"


def test_unwraps_suffix_matched_domain():
    wrapped = "https://tenant123.shim.example/go?u=https%3A%2F%2Freal.example%2F"
    result = clean_url(wrapped, _lists())
    assert result.unwrapped_redirect is True
    assert result.cleaned == "https://real.example/"


def test_does_not_unwrap_unknown_domain():
    url = "https://notwrapped.example/go?url=https://real.example/path"
    result = clean_url(url, _lists())
    assert result.unwrapped_redirect is False
    assert result.cleaned == url


def test_preserves_explicit_empty_value_params():
    # round 1 finding: "a=" (explicit, empty value) must not collapse to
    # the flag form "a" (no '=' at all) -- they're different inputs.
    url = "https://example.com/path?a=&b=1&flag"
    result = clean_url(url, _lists())
    assert result.cleaned == url


def test_preserves_bare_trailing_query_and_fragment_markers():
    # feature 7's idempotency fuzz found this: a literal trailing '?' or
    # '#' with nothing after it, and nothing removed, must survive
    # byte-for-byte -- it's not our content to delete.
    lists = _lists()
    assert clean_url("https://example.com/path?", lists).cleaned == "https://example.com/path?"
    assert clean_url("https://example.com/path#", lists).cleaned == "https://example.com/path#"
    # but a '?' that only ever held tracking params is still dropped once
    # they're removed -- that's the existing, desired cleanup.
    assert clean_url("https://example.com/path?utm_source=x", lists).cleaned == "https://example.com/path"


def test_malformed_ipv6_bracket_does_not_raise():
    # round 3's fuzz test found this: urlsplit() raises ValueError on an
    # unbalanced '['/']' in the host instead of returning. Must be treated
    # like any other not-really-a-URL input: passed through unchanged.
    url = "https://[::1/path?utm_source=x"
    result = clean_url(url, _lists())
    assert result.cleaned == url
    assert result.removed_params == []


def test_real_list_strips_amazon_recommendation_widget_params():
    # round 11 finding: this went completely untouched on the first pass,
    # caught only by generating the example gallery against the real list.
    lists = TrackerLists.from_files()
    url = (
        "https://www.amazon.com/dp/B08N5WRWNW?ref=sxts_klp_1&_encoding=UTF8"
        "&pd_rd_i=B08N5WRWNW&pd_rd_r=abc123&pf_rd_p=1&pf_rd_r=2"
    )
    result = clean_url(url, lists)
    assert result.cleaned == "https://www.amazon.com/dp/B08N5WRWNW?_encoding=UTF8"
    assert set(result.removed_params) == {"ref", "pd_rd_i", "pd_rd_r", "pf_rd_p", "pf_rd_r"}


def test_real_data_files_load():
    # the shipped lists, not the fixture -- sanity check data/ actually parses
    lists = TrackerLists.from_files()
    assert "utm_" in lists.param_prefixes
    assert "fbclid" in lists.params
    assert lists.redirect_domains or lists.redirect_domain_suffixes
