//! Integration tests for the `link_scrub` CLI binary itself (argv parsing,
//! --help/--version/error paths, stdin mode). Round 13 of the critique
//! ledger: round 5 rewrote all of this and it had zero automated coverage,
//! only a one-time manual check -- nothing would have caught a regression.
//! Uses `env!("CARGO_BIN_EXE_link_scrub")`, which Cargo provides to
//! integration tests automatically; no extra dependency needed.

use std::io::Write;
use std::process::{Command, Stdio};

fn bin() -> &'static str {
    env!("CARGO_BIN_EXE_link_scrub")
}

#[test]
fn help_prints_usage_and_exits_zero() {
    let output = Command::new(bin()).arg("--help").output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("USAGE"));
    assert!(stdout.contains("link_scrub"));
}

#[test]
fn short_help_flag_works_too() {
    let output = Command::new(bin()).arg("-h").output().unwrap();
    assert!(output.status.success());
    assert!(String::from_utf8_lossy(&output.stdout).contains("USAGE"));
}

#[test]
fn version_prints_and_exits_zero() {
    let output = Command::new(bin()).arg("-V").output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.trim().starts_with("link_scrub "));
}

#[test]
fn unrecognized_flag_errors_with_nonzero_exit() {
    let output = Command::new(bin()).arg("--bogus-flag").output().unwrap();
    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("unrecognized option"));
}

#[test]
fn cleans_url_given_as_argv() {
    let output = Command::new(bin())
        .arg("https://example.com/a?utm_source=x&id=1")
        .output()
        .unwrap();
    assert!(output.status.success());
    assert_eq!(
        String::from_utf8_lossy(&output.stdout).trim(),
        "https://example.com/a?id=1"
    );
}

#[test]
fn verbose_flag_reports_removed_params_on_stderr() {
    let output = Command::new(bin())
        .args(["-v", "https://example.com/a?utm_source=x"])
        .output()
        .unwrap();
    assert!(output.status.success());
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "https://example.com/a");
    assert!(String::from_utf8_lossy(&output.stderr).contains("removed: utm_source"));
}

#[test]
fn reads_multiple_urls_from_stdin_when_no_argv_urls_given() {
    let mut child = Command::new(bin())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(b"https://example.com/a?utm_source=x\nhttps://example.com/b?id=2\n")
        .unwrap();
    let output = child.wait_with_output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    let lines: Vec<&str> = stdout.lines().collect();
    assert_eq!(lines, vec!["https://example.com/a", "https://example.com/b?id=2"]);
}
