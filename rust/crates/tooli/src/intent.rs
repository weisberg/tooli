//! Single source of truth for "what does this CLI invocation want?"
//!
//! Before Clap parses argv we need to recognize three special intents:
//!
//! - `--agent-manifest` / `--help-agent` (root manifest export),
//! - `<command> --schema` (per-command schema export, even when the command
//!   has required positional arguments Clap would otherwise reject),
//! - any other invocation → run normally.
//!
//! Earlier versions of this crate had three separate hand-rolled walks of
//! `env::args()` (one per intent, plus a third for "is machine output requested
//! before Clap fails parsing"). They each maintained an independent list of
//! global flags and how to skip them, which is exactly the kind of duplication
//! that drifts out of sync the moment a new global flag is added. This module
//! is the one place that knows the global-flag shape pre-parse.

use crate::output::OutputMode;
use std::env;
use std::str::FromStr;

/// Result of pre-parsing `env::args()` to detect special intents.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Intent<'a> {
    /// Emit the per-command schema for the given command name.
    Schema(&'a str),
    /// Emit the root agent manifest.
    AgentManifest,
    /// Run normally; let Clap handle the rest.
    Run,
}

/// Detect the current invocation's intent by walking `env::args()` once.
pub fn detect<'a>(commands: &'a [&'a str]) -> Intent<'a> {
    detect_from_args(env::args().skip(1), commands)
}

/// Same as [`detect`] but with explicit argument tokens (testable).
pub fn detect_from_args<'a, I, S>(args: I, commands: &'a [&'a str]) -> Intent<'a>
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let tokens: Vec<String> = args.into_iter().map(|s| s.as_ref().to_string()).collect();

    if tokens
        .iter()
        .any(|arg| arg == "--agent-manifest" || arg == "--help-agent")
    {
        return Intent::AgentManifest;
    }

    if !tokens.iter().any(|arg| arg == "--schema") {
        return Intent::Run;
    }

    let mut index = 0;
    while index < tokens.len() {
        let arg = tokens[index].as_str();
        if arg == "--" {
            return Intent::Run;
        }
        if global_flag_takes_value(arg) {
            index += 2;
            continue;
        }
        if global_bool_flag(arg) || arg.starts_with("--output=") {
            index += 1;
            continue;
        }
        if let Some(matched) = commands.iter().copied().find(|name| *name == arg) {
            return Intent::Schema(matched);
        }
        // Unknown token: not a global flag, not a known subcommand. Could be
        // a positional value for a subcommand that was already consumed; keep
        // walking.
        index += 1;
    }

    Intent::Run
}

/// Return true when argv or environment requests a machine-readable output
/// mode before Clap has a chance to parse `GlobalOptions`.
///
/// Used by `App::exit_for_clap_error` so that parse failures still surface as
/// JSON envelopes when a caller asked for them.
pub fn machine_output_requested() -> bool {
    let mut args = env::args().peekable();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--json" | "--jsonl" | "--agent-manifest" | "--help-agent" => return true,
            "--output" | "-o" => {
                if matches!(args.peek().map(String::as_str), Some("json" | "jsonl")) {
                    return true;
                }
            }
            value if value == "--output=json" || value == "--output=jsonl" => return true,
            _ => {}
        }
    }

    env::var("TOOLI_OUTPUT")
        .ok()
        .and_then(|raw| OutputMode::from_str(raw.as_str()).ok())
        .is_some_and(|mode| matches!(mode, OutputMode::Json | OutputMode::Jsonl))
        || crate::output::env_flag_enabled("TOOLI_AGENT_MODE")
}

/// Long flag that consumes the next argument as its value.
///
/// Adding a new global value-flag means updating this list. The list of
/// boolean flags is also defined here, in [`global_bool_flag`].
fn global_flag_takes_value(arg: &str) -> bool {
    matches!(arg, "--output" | "-o")
}

/// Long flag (or short cluster) that does not consume the next argument.
fn global_bool_flag(arg: &str) -> bool {
    matches!(
        arg,
        "--json"
            | "--jsonl"
            | "--text"
            | "--plain"
            | "--no-color"
            | "--quiet"
            | "-q"
            | "--verbose"
            | "--dry-run"
            | "--yes"
            | "-y"
            | "--schema"
            | "--agent-manifest"
            | "--help-agent"
    ) || short_verbose_cluster(arg)
}

fn short_verbose_cluster(arg: &str) -> bool {
    arg.strip_prefix('-')
        .is_some_and(|rest| !rest.is_empty() && rest.chars().all(|ch| ch == 'v'))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn schema_intent_finds_first_command_after_global_flags() {
        let intent = detect_from_args(
            ["--json", "--output", "json", "find", "--schema"],
            &["find", "read"],
        );
        assert_eq!(intent, Intent::Schema("find"));
    }

    #[test]
    fn schema_intent_uses_subcommand_not_argument_text() {
        let intent = detect_from_args(["read", "find", "--schema"], &["find", "read"]);
        assert_eq!(intent, Intent::Schema("read"));
    }

    #[test]
    fn no_schema_returns_run() {
        let intent = detect_from_args(["find", "*.rs"], &["find", "read"]);
        assert_eq!(intent, Intent::Run);
    }

    #[test]
    fn manifest_short_circuits_schema() {
        let intent = detect_from_args(["--agent-manifest", "find", "--schema"], &["find", "read"]);
        assert_eq!(intent, Intent::AgentManifest);
    }

    #[test]
    fn double_dash_terminates_intent_search() {
        let intent = detect_from_args(["--", "find", "--schema"], &["find", "read"]);
        assert_eq!(intent, Intent::Run);
    }
}
