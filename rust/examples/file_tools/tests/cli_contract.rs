use assert_cmd::Command;
use serde_json::Value;
use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

fn cargo_bin() -> Command {
    Command::cargo_bin("file_tools").expect("file_tools binary should build")
}

fn workspace_src() -> String {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../crates/tooli/src")
        .canonicalize()
        .expect("workspace source path should exist")
        .display()
        .to_string()
}

fn temp_text_file(contents: &str) -> String {
    let suffix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should be after epoch")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("tooli-rs-test-{suffix}.txt"));
    fs::write(&path, contents).expect("temp file should be writable");
    path.display().to_string()
}

#[test]
fn find_emits_success_envelope() {
    let output = cargo_bin()
        .args(["find", "*.rs", "--root", &workspace_src(), "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
    assert_eq!(payload["meta"]["tool"], "file-tools.find");
    assert!(payload["result"]
        .as_array()
        .is_some_and(|items| !items.is_empty()));
}

#[test]
fn tooli_output_env_can_request_json() {
    let output = cargo_bin()
        .env("TOOLI_OUTPUT", "json")
        .args(["find", "*.rs", "--root", &workspace_src()])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
    assert_eq!(payload["meta"]["tool"], "file-tools.find");
}

#[test]
fn tooli_agent_mode_env_can_request_json() {
    let output = cargo_bin()
        .env("TOOLI_AGENT_MODE", "1")
        .args(["find", "*.rs", "--root", &workspace_src()])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
    assert_eq!(payload["meta"]["tool"], "file-tools.find");
}

#[test]
fn global_json_flag_works_before_subcommand() {
    let output = cargo_bin()
        .args(["--json", "find", "*.rs", "--root", &workspace_src()])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
    assert_eq!(payload["meta"]["tool"], "file-tools.find");
}

#[test]
fn tooli_caller_env_is_included_in_meta() {
    let output = cargo_bin()
        .env("TOOLI_CALLER", "codex")
        .args(["find", "*.rs", "--root", &workspace_src(), "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["meta"]["caller_id"], "codex");
}

#[test]
fn allowed_capability_permits_command() {
    let output = cargo_bin()
        .env("TOOLI_ALLOWED_CAPABILITIES", "fs:read")
        .args(["find", "meta.rs", "--root", &workspace_src(), "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
}

#[test]
fn namespace_wildcard_capability_permits_command() {
    let output = cargo_bin()
        .env("TOOLI_ALLOWED_CAPABILITIES", "fs:*")
        .args(["find", "meta.rs", "--root", &workspace_src(), "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
}

#[test]
fn denied_capability_blocks_before_business_logic() {
    let output = cargo_bin()
        .env("TOOLI_ALLOWED_CAPABILITIES", "net:read")
        .args(["find", "meta.rs", "--root", &workspace_src(), "--json"])
        .assert()
        .code(30)
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], false);
    assert_eq!(payload["error"]["category"], "auth");
    assert_eq!(payload["error"]["code"], "E2001");
    assert_eq!(payload["error"]["details"]["required"][0], "fs:read");
    assert_eq!(payload["error"]["details"]["missing"][0], "fs:read");
}

#[test]
fn dry_run_flag_is_reflected_in_meta() {
    let output = cargo_bin()
        .args([
            "find",
            "*.rs",
            "--root",
            &workspace_src(),
            "--json",
            "--dry-run",
        ])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["meta"]["dry_run"], true);
}

#[test]
fn jsonl_emits_one_envelope_per_result() {
    let output = cargo_bin()
        .args(["find", "*.rs", "--root", &workspace_src(), "--jsonl"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let stdout = String::from_utf8(output).expect("stdout should be utf8");
    let lines: Vec<&str> = stdout.lines().collect();

    assert!(!lines.is_empty());
    for line in lines {
        let payload: Value = serde_json::from_str(line).expect("line should be JSON");
        assert_eq!(payload["ok"], true);
        assert_eq!(payload["meta"]["tool"], "file-tools.find");
        assert!(payload["result"]["path"]
            .as_str()
            .is_some_and(|path| path.ends_with(".rs")));
    }
}

#[test]
fn no_matches_are_a_successful_empty_result() {
    let output = cargo_bin()
        .args([
            "find",
            "*.definitely-missing",
            "--root",
            &workspace_src(),
            "--json",
        ])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
    assert_eq!(
        payload["result"]
            .as_array()
            .expect("result should be array")
            .len(),
        0
    );
}

#[test]
fn find_schema_does_not_require_business_args() {
    let output = cargo_bin()
        .args(["find", "--schema"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["name"], "find");
    assert_eq!(payload["annotations"]["readOnlyHint"], true);
    assert_eq!(payload["annotations"]["idempotentHint"], true);
    assert_eq!(payload["capabilities"][0], "fs:read");
    assert_eq!(payload["inputSchema"]["properties"]["root"]["default"], ".");
    assert_eq!(payload["outputSchema"]["type"], "array");
    assert!(payload["inputSchema"]["required"]
        .as_array()
        .expect("required should be an array")
        .contains(&Value::String("pattern".to_string())));

    let rendered = serde_json::to_string(&payload).expect("schema should render");
    assert!(!rendered.contains("\"$ref\""));
    assert!(!rendered.contains("\"definitions\""));
}

#[test]
fn read_schema_shows_input_source_shape() {
    let output = cargo_bin()
        .args(["read", "--schema"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["name"], "read");
    assert_eq!(
        payload["inputSchema"]["properties"]["source"]["type"],
        "string"
    );
    assert!(
        payload["inputSchema"]["properties"]["source"]["description"]
            .as_str()
            .is_some_and(|description| description.contains("stdin"))
    );
    assert_eq!(payload["capabilities"][0], "fs:read");
}

#[test]
fn schema_bypass_uses_actual_subcommand_not_argument_text() {
    let output = cargo_bin()
        .args(["read", "find", "--schema"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["name"], "read");
    assert!(payload["inputSchema"]["properties"]
        .as_object()
        .unwrap()
        .contains_key("source"));
}

#[test]
fn read_command_summarizes_file_input_source() {
    let path = temp_text_file("alpha\nbeta\n");
    let output = cargo_bin()
        .args(["read", &path, "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
    assert_eq!(payload["meta"]["tool"], "file-tools.read");
    assert_eq!(payload["result"]["bytes"], 11);
    assert_eq!(payload["result"]["lines"], 2);
    assert_eq!(payload["result"]["preview"], "alpha\nbeta\n");
}

#[test]
fn read_command_accepts_stdin_source() {
    let output = cargo_bin()
        .args(["read", "-", "--json"])
        .write_stdin("one\ntwo\nthree\n")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
    assert_eq!(payload["result"]["lines"], 3);
}

#[test]
fn agent_manifest_describes_every_command_and_global_agent_flags() {
    let output = cargo_bin()
        .args(["--agent-manifest"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["name"], "file-tools");
    assert_eq!(payload["non_interactive"], true);
    assert_eq!(payload["schema_version"], "1.0");
    assert_eq!(payload["commands"].as_array().unwrap().len(), 2);
    assert!(payload["commands"]
        .as_array()
        .unwrap()
        .iter()
        .any(|command| command["name"] == "find"));
    assert!(payload["commands"]
        .as_array()
        .unwrap()
        .iter()
        .any(|command| command["name"] == "read"));
    assert!(payload["global_flags"]
        .as_array()
        .unwrap()
        .iter()
        .any(|flag| flag["name"] == "--json"));
    assert!(payload["global_flags"]
        .as_array()
        .unwrap()
        .iter()
        .any(|flag| flag["name"] == "--agent-manifest"));
    assert!(payload["skill"]["rules"]
        .as_array()
        .unwrap()
        .iter()
        .any(|rule| rule
            .as_str()
            .unwrap()
            .contains("Never rely on interactive prompts")));
}

#[test]
fn help_agent_alias_emits_agent_manifest() {
    let output = cargo_bin()
        .args(["--help-agent"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["name"], "file-tools");
    assert_eq!(
        payload["skill"]["discovery_command"],
        "file-tools --agent-manifest"
    );
}

#[test]
fn missing_command_in_json_mode_returns_structured_error() {
    let output = cargo_bin()
        .args(["--json"])
        .assert()
        .code(2)
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], false);
    assert_eq!(payload["error"]["category"], "input");
    assert!(payload["error"]["suggestion"]["fix"]
        .as_str()
        .unwrap()
        .contains("--agent-manifest"));
}

#[test]
fn missing_command_in_agent_mode_returns_structured_error() {
    let output = cargo_bin()
        .env("TOOLI_AGENT_MODE", "1")
        .assert()
        .code(2)
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], false);
    assert_eq!(payload["error"]["category"], "input");
    assert!(payload["error"]["suggestion"]["fix"]
        .as_str()
        .unwrap()
        .contains("--agent-manifest"));
}

#[test]
fn invalid_pattern_emits_structured_error() {
    let output = cargo_bin()
        .args(["find", "", "--json"])
        .assert()
        .code(2)
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], false);
    assert_eq!(payload["error"]["category"], "input");
    assert_eq!(payload["error"]["code"], "E1001");
    assert_eq!(payload["error"]["field"], "pattern");
    assert_eq!(
        payload["error"]["suggestion"]["action"],
        "retry_with_modified_input"
    );
    assert_eq!(payload["result"], Value::Null);
}

#[test]
fn missing_root_emits_state_error_and_exit_10() {
    let output = cargo_bin()
        .args(["find", "*.rs", "--root", "__missing_root__", "--json"])
        .assert()
        .code(10)
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], false);
    assert_eq!(payload["error"]["category"], "state");
    assert_eq!(payload["error"]["code"], "E3001");
    assert_eq!(payload["error"]["field"], "root");
}

#[test]
fn clap_parse_errors_become_json_when_machine_output_requested() {
    let output = cargo_bin()
        .args(["find", "--json"])
        .assert()
        .code(2)
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], false);
    assert_eq!(payload["error"]["category"], "input");
    assert_eq!(payload["error"]["code"], "E1001");
    assert!(payload["error"]["message"]
        .as_str()
        .is_some_and(|message| message.contains("required arguments")));
}

#[test]
fn find_text_output_uses_human_render_override() {
    // FindArgs implements `Command::render_human` to emit one path per line.
    // This proves the override path is wired through `App::run_command`.
    let output = cargo_bin()
        .args(["find", "meta.rs", "--root", &workspace_src(), "--text"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let stdout = String::from_utf8(output).expect("stdout should be utf8");

    assert!(stdout.contains("meta.rs"));
    assert!(!stdout.contains("\"ok\""));
    assert!(!stdout.contains("\"meta\""));
    // The override emits paths only — no JSON braces.
    assert!(!stdout.contains('{'));
}

#[test]
fn output_flag_json_matches_json_alias() {
    let output = cargo_bin()
        .args([
            "find",
            "meta.rs",
            "--root",
            &workspace_src(),
            "--output",
            "json",
        ])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let payload: Value = serde_json::from_slice(&output).expect("stdout should be JSON");

    assert_eq!(payload["ok"], true);
    assert!(payload["result"][0]["path"]
        .as_str()
        .unwrap()
        .ends_with("meta.rs"));
}
