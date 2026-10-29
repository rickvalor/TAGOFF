//! Integration tests for the `tagoff` CLI binary itself (argv parsing,
//! --help/--version/error paths, stdin mode). Round 13 of the critique
//! ledger: round 5 rewrote all of this and it had zero automated coverage,
//! only a one-time manual check -- nothing would have caught a regression.
//! Uses `env!("CARGO_BIN_EXE_tagoff")`, which Cargo provides to
//! integration tests automatically; no extra dependency needed.

use std::io::Write;
use std::process::{Command, Stdio};

fn bin() -> &'static str {
    env!("CARGO_BIN_EXE_tagoff")
}

#[test]
fn help_prints_usage_and_exits_zero() {
    let output = Command::new(bin()).arg("--help").output().unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("USAGE"));
    assert!(stdout.contains("tagoff"));
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
    assert!(stdout.trim().starts_with("tagoff "));
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
fn diff_mode_shows_minus_plus_for_changed_and_unchanged_marker_otherwise() {
    let output = Command::new(bin())
        .args(["--diff", "https://example.com/a?utm_source=x", "https://example.com/b?id=1"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("- https://example.com/a?utm_source=x"));
    assert!(stdout.contains("+ https://example.com/a"));
    assert!(stdout.contains("unchanged: https://example.com/b?id=1"));
}

#[test]
fn input_and_output_files_round_trip() {
    let dir = std::env::temp_dir().join(format!("tagoff_cli_io_test_{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let input_path = dir.join("in.txt");
    let output_path = dir.join("out.txt");
    std::fs::write(&input_path, "https://example.com/a?utm_source=x\nhttps://example.com/b?id=1\n").unwrap();

    let output = Command::new(bin())
        .arg("--input")
        .arg(&input_path)
        .arg("--output")
        .arg(&output_path)
        .output()
        .unwrap();
    assert!(output.status.success());
    assert_eq!(String::from_utf8_lossy(&output.stdout), "");

    let written = std::fs::read_to_string(&output_path).unwrap();
    assert_eq!(written, "https://example.com/a\nhttps://example.com/b?id=1\n");

    // no leftover temp file from the atomic-write dance
    let leftovers: Vec<_> = std::fs::read_dir(&dir)
        .unwrap()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_name().to_string_lossy().starts_with(".tagoff_tmp_"))
        .collect();
    assert!(leftovers.is_empty());
    std::fs::remove_dir_all(&dir).ok();
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
