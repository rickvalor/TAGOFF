//! Raw C-ABI WASM wrapper around `link_scrub::clean_url`, for the static
//! browser demo in `web_demo/`. No `wasm-bindgen` -- this crate's whole
//! reason to exist is to prove the core logic runs in a browser with
//! nothing but hand-written JS glue talking to WASM linear memory
//! directly. Single-threaded, single-user-at-a-time by design (one global
//! `LISTS`), which is exactly right for a page running in one visitor's
//! own browser tab.

use link_scrub::{clean_url, TrackerLists};
use std::alloc::{alloc, dealloc, Layout};
use std::sync::OnceLock;

static LISTS: OnceLock<TrackerLists> = OnceLock::new();

/// Allocate `len` bytes in WASM linear memory and return the pointer, so
/// JS can write the tracker-list text (or a URL to clean) into memory it
/// owns before calling into Rust. The demo page never calls `free` on
/// these -- it's a handful of small allocations for the lifetime of one
/// page load, not a long-running process; leaking is the deliberate,
/// documented tradeoff for a browser-tab demo, not an oversight.
#[no_mangle]
pub extern "C" fn alloc_buffer(len: usize) -> *mut u8 {
    if len == 0 {
        return std::ptr::null_mut();
    }
    unsafe { alloc(Layout::from_size_align(len, 1).unwrap_or_else(|_| Layout::new::<u8>())) }
}

#[no_mangle]
pub extern "C" fn free_buffer(ptr: *mut u8, len: usize) {
    if ptr.is_null() || len == 0 {
        return;
    }
    unsafe { dealloc(ptr, Layout::from_size_align(len, 1).unwrap_or_else(|_| Layout::new::<u8>())) };
}

/// Load the tracker lists once per page load, from their text content
/// (JS fetches `data/tracking_params.txt`/`tracking_domains.txt` and
/// writes the bytes into buffers allocated via `alloc_buffer`).
#[no_mangle]
pub unsafe extern "C" fn init_lists(
    params_ptr: *const u8,
    params_len: usize,
    domains_ptr: *const u8,
    domains_len: usize,
) {
    let params = std::str::from_utf8(std::slice::from_raw_parts(params_ptr, params_len)).unwrap_or("");
    let domains = std::str::from_utf8(std::slice::from_raw_parts(domains_ptr, domains_len)).unwrap_or("");
    let _ = LISTS.set(TrackerLists::from_lines(params, domains));
}

/// Clean one URL. `url_ptr`/`url_len` point at the input (written by JS
/// via `alloc_buffer`); `out_len_ptr` is a 4-byte buffer JS also
/// allocates, which this writes the output length into. Returns a
/// pointer to the cleaned UTF-8 bytes.
#[no_mangle]
pub unsafe extern "C" fn clean(url_ptr: *const u8, url_len: usize, out_len_ptr: *mut usize) -> *mut u8 {
    let url = std::str::from_utf8(std::slice::from_raw_parts(url_ptr, url_len)).unwrap_or("");
    let lists = match LISTS.get() {
        Some(l) => l,
        None => {
            *out_len_ptr = 0;
            return std::ptr::null_mut();
        }
    };
    let result = clean_url(url, lists, 3);
    let bytes = result.cleaned.into_bytes();
    *out_len_ptr = bytes.len();
    if bytes.is_empty() {
        return std::ptr::null_mut();
    }
    let ptr = alloc_buffer(bytes.len());
    std::ptr::copy_nonoverlapping(bytes.as_ptr(), ptr, bytes.len());
    ptr
}
