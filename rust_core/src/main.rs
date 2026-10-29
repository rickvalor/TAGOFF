//! CLI for tagoff. Cleans URLs given as arguments, or one per line on
//! stdin if none are given.
//!
//! The tracker lists are compiled into the binary (`include_str!`) so the
//! CLI works from anywhere with no runtime path resolution -- edit
//! `data/tracking_params.txt` or `data/tracking_domains.txt` and rebuild to
//! pick up changes.

use tagoff::{clean_url, json_escape, read_overlay, user_config_dir, CleanResult, TrackerLists};
use std::io::{self, BufRead, Write};
use std::path::PathBuf;
use std::process::ExitCode;

const PARAMS_TXT: &str = include_str!("../../data/tracking_params.txt");
const DOMAINS_TXT: &str = include_str!("../../data/tracking_domains.txt");
const MAX_UNWRAP_DEPTH: u8 = 3;

const USAGE: &str = "\
tagoff -- strip tracking query params from URLs and unwrap known link-shim redirectors.

USAGE:
    tagoff [OPTIONS] [URL ...]

    With no URLs given, reads one URL per line from stdin (or --input).

OPTIONS:
    -v, --verbose      print what was removed/unwrapped, to stderr
        --json         emit one JSON object per line instead of plain text
        --diff         show '- original' / '+ cleaned' pairs instead of just the result
        --stats        print an aggregate summary to stderr after processing
        --check        exit 1 if any URL had tracking to remove (CI/pre-commit gate)
        --list-params  print the loaded tracking-param rules and exit
        --list-domains print the loaded redirector-domain rules and exit
        --input FILE   read URLs from this file (one per line) instead of stdin
        --output FILE  write cleaned URLs to this file instead of stdout (atomic write)
    -h, --help         print this message and exit
    -V, --version      print the version and exit";

#[derive(Default)]
struct Options {
    verbose: bool,
    json: bool,
    diff: bool,
    stats: bool,
    check: bool,
    list_params: bool,
    list_domains: bool,
    input: Option<PathBuf>,
    output: Option<PathBuf>,
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "-h" || a == "--help") {
        println!("{USAGE}");
        return ExitCode::SUCCESS;
    }
    if args.iter().any(|a| a == "-V" || a == "--version") {
        println!("tagoff {}", env!("CARGO_PKG_VERSION"));
        return ExitCode::SUCCESS;
    }

    let mut opts = Options::default();
    let mut urls: Vec<String> = Vec::new();
    let mut iter = args.iter();
    while let Some(arg) = iter.next() {
        match arg.as_str() {
            "-v" | "--verbose" => opts.verbose = true,
            "--json" => opts.json = true,
            "--diff" => opts.diff = true,
            "--stats" => opts.stats = true,
            "--check" => opts.check = true,
            "--list-params" => opts.list_params = true,
            "--list-domains" => opts.list_domains = true,
            "--input" => match iter.next() {
                Some(v) => opts.input = Some(PathBuf::from(v)),
                None => {
                    eprintln!("tagoff: --input requires a file path\n\n{USAGE}");
                    return ExitCode::FAILURE;
                }
            },
            "--output" => match iter.next() {
                Some(v) => opts.output = Some(PathBuf::from(v)),
                None => {
                    eprintln!("tagoff: --output requires a file path\n\n{USAGE}");
                    return ExitCode::FAILURE;
                }
            },
            other if other.starts_with('-') && other.len() > 1 => {
                eprintln!("tagoff: unrecognized option '{other}'\n\n{USAGE}");
                return ExitCode::FAILURE;
            }
            other => urls.push(other.to_string()),
        }
    }

    let mut lists = TrackerLists::from_lines(PARAMS_TXT, DOMAINS_TXT);
    if let Some(dir) = user_config_dir() {
        let (extra_params, extra_domains) = read_overlay(&dir);
        lists.extend_from_lines(&extra_params, &extra_domains);
    }

    if opts.list_params {
        for line in lists.describe_params() {
            println!("{line}");
        }
        return ExitCode::SUCCESS;
    }
    if opts.list_domains {
        for line in lists.describe_domains() {
            println!("{line}");
        }
        return ExitCode::SUCCESS;
    }

    let input_lines: Vec<String> = match &opts.input {
        Some(path) => match std::fs::read_to_string(path) {
            Ok(text) => text.lines().map(|l| l.to_string()).collect(),
            Err(e) => {
                eprintln!("tagoff: could not read {path:?}: {e}");
                return ExitCode::FAILURE;
            }
        },
        None => Vec::new(),
    };

    let mut any_tracking_found = false;
    let mut total = 0u64;
    let mut total_removed = 0u64;
    let mut total_unwrapped = 0u64;
    let mut param_counts: std::collections::HashMap<String, u64> = std::collections::HashMap::new();
    let mut buffered: Vec<String> = Vec::new();

    // Buffering is only needed for --output's atomic write; the default
    // stdout path stays streaming, same as before --output existed --
    // large stdin batches shouldn't need to fit in memory just because
    // --output is an option.
    let stdout = io::stdout();
    let mut stdout_lock = stdout.lock();
    let mut process = |line: &str, buffered: &mut Vec<String>, out: &mut io::StdoutLock| {
        let result = clean_url(line, &lists, MAX_UNWRAP_DEPTH);
        total += 1;
        if result.unwrapped_redirect {
            total_unwrapped += 1;
        }
        if !result.removed_params.is_empty() || result.unwrapped_redirect {
            any_tracking_found = true;
        }
        for p in &result.removed_params {
            total_removed += 1;
            *param_counts.entry(p.to_ascii_lowercase()).or_insert(0) += 1;
        }
        let formatted = format_result(&result, &opts);
        if opts.output.is_some() {
            buffered.push(formatted);
        } else {
            writeln!(out, "{formatted}").ok();
        }
    };

    if !urls.is_empty() {
        for url in &urls {
            process(url, &mut buffered, &mut stdout_lock);
        }
    } else if opts.input.is_some() {
        for line in &input_lines {
            if line.trim().is_empty() {
                continue;
            }
            process(line, &mut buffered, &mut stdout_lock);
        }
    } else {
        let stdin = io::stdin();
        for line in stdin.lock().lines() {
            let line = line.unwrap_or_default();
            if line.trim().is_empty() {
                continue;
            }
            process(&line, &mut buffered, &mut stdout_lock);
        }
    }
    drop(process);

    if let Some(path) = &opts.output {
        let mut content = buffered.join("\n");
        if !buffered.is_empty() {
            content.push('\n');
        }
        if let Err(e) = atomic_write(path, &content) {
            eprintln!("tagoff: could not write {path:?}: {e}");
            return ExitCode::FAILURE;
        }
    }

    if opts.stats {
        print_stats(total, total_removed, total_unwrapped, &param_counts);
    }

    if opts.check && any_tracking_found {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}

fn atomic_write(path: &std::path::Path, content: &str) -> io::Result<()> {
    let dir = path.parent().filter(|p| !p.as_os_str().is_empty()).unwrap_or_else(|| std::path::Path::new("."));
    let tmp_path = dir.join(format!(".tagoff_tmp_{}", std::process::id()));
    std::fs::write(&tmp_path, content)?;
    std::fs::rename(&tmp_path, path)
}

fn format_result(result: &CleanResult, opts: &Options) -> String {
    if opts.json {
        let removed = result
            .removed_params
            .iter()
            .map(|p| format!("\"{}\"", json_escape(p)))
            .collect::<Vec<_>>()
            .join(",");
        return format!(
            "{{\"original\":\"{}\",\"cleaned\":\"{}\",\"unwrapped_redirect\":{},\"removed_params\":[{}]}}",
            json_escape(&result.original),
            json_escape(&result.cleaned),
            result.unwrapped_redirect,
            removed
        );
    }
    if opts.diff {
        if result.cleaned == result.original {
            return format!("  unchanged: {}", result.original);
        }
        return format!("- {}\n+ {}", result.original, result.cleaned);
    }
    if opts.verbose {
        if result.unwrapped_redirect {
            eprintln!("  unwrapped redirect: {}", result.original);
        }
        if !result.removed_params.is_empty() {
            eprintln!("  removed: {}", result.removed_params.join(", "));
        }
    }
    result.cleaned.clone()
}

fn print_stats(
    total: u64,
    total_removed: u64,
    total_unwrapped: u64,
    param_counts: &std::collections::HashMap<String, u64>,
) {
    eprintln!("--- tagoff stats ---");
    eprintln!("URLs processed:        {total}");
    eprintln!("Tracking params removed: {total_removed}");
    eprintln!("Redirectors unwrapped: {total_unwrapped}");
    if !param_counts.is_empty() {
        let mut counts: Vec<(&String, &u64)> = param_counts.iter().collect();
        counts.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
        eprintln!("Top removed params:");
        for (name, count) in counts.into_iter().take(10) {
            eprintln!("  {name}: {count}");
        }
    }
}
