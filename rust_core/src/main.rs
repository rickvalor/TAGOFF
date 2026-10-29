//! CLI for link_scrub. Cleans URLs given as arguments, or one per line on
//! stdin if none are given.
//!
//! The tracker lists are compiled into the binary (`include_str!`) so the
//! CLI works from anywhere with no runtime path resolution -- edit
//! `data/tracking_params.txt` or `data/tracking_domains.txt` and rebuild to
//! pick up changes.

use link_scrub::{clean_url, TrackerLists};
use std::io::{self, BufRead, Write};
use std::process::ExitCode;

const PARAMS_TXT: &str = include_str!("../../data/tracking_params.txt");
const DOMAINS_TXT: &str = include_str!("../../data/tracking_domains.txt");
const MAX_UNWRAP_DEPTH: u8 = 3;

const USAGE: &str = "\
link_scrub -- strip tracking query params from URLs and unwrap known link-shim redirectors.

USAGE:
    link_scrub [OPTIONS] [URL ...]

    With no URLs given, reads one URL per line from stdin.

OPTIONS:
    -v, --verbose    print what was removed/unwrapped, to stderr
    -h, --help       print this message and exit
    -V, --version    print the version and exit";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "-h" || a == "--help") {
        println!("{USAGE}");
        return ExitCode::SUCCESS;
    }
    if args.iter().any(|a| a == "-V" || a == "--version") {
        println!("link_scrub {}", env!("CARGO_PKG_VERSION"));
        return ExitCode::SUCCESS;
    }

    let mut verbose = false;
    let mut urls: Vec<String> = Vec::new();
    for arg in &args {
        match arg.as_str() {
            "-v" | "--verbose" => verbose = true,
            other if other.starts_with('-') && other.len() > 1 => {
                eprintln!("link_scrub: unrecognized option '{other}'\n\n{USAGE}");
                return ExitCode::FAILURE;
            }
            other => urls.push(other.to_string()),
        }
    }

    let lists = TrackerLists::from_lines(PARAMS_TXT, DOMAINS_TXT);
    let stdout = io::stdout();
    let mut out = stdout.lock();

    if urls.is_empty() {
        let stdin = io::stdin();
        for line in stdin.lock().lines() {
            let line = line.unwrap_or_default();
            if line.trim().is_empty() {
                continue;
            }
            emit(&line, &lists, verbose, &mut out);
        }
    } else {
        for url in &urls {
            emit(url, &lists, verbose, &mut out);
        }
    }
    ExitCode::SUCCESS
}

fn emit(url: &str, lists: &TrackerLists, verbose: bool, out: &mut impl Write) {
    let result = clean_url(url, lists, MAX_UNWRAP_DEPTH);
    writeln!(out, "{}", result.cleaned).ok();
    if verbose {
        if result.unwrapped_redirect {
            eprintln!("  unwrapped redirect: {}", result.original);
        }
        if !result.removed_params.is_empty() {
            eprintln!("  removed: {}", result.removed_params.join(", "));
        }
    }
}
