//! Output mode parsing and resolution from flags / environment / TTY state.

use clap::{Args, ValueEnum};
use serde::Serialize;
use std::env;
use std::io::{self, IsTerminal};
use std::str::FromStr;

/// Output modes supported by the Rust Tooli runtime.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, ValueEnum)]
#[serde(rename_all = "snake_case")]
pub enum OutputMode {
    Auto,
    Json,
    Jsonl,
    Text,
    Plain,
}

impl FromStr for OutputMode {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value.trim().to_ascii_lowercase().as_str() {
            "auto" => Ok(Self::Auto),
            "json" => Ok(Self::Json),
            "jsonl" => Ok(Self::Jsonl),
            "text" => Ok(Self::Text),
            "plain" => Ok(Self::Plain),
            other => Err(format!("unknown output mode: {other}")),
        }
    }
}

/// Global Tooli flags that can be flattened into a Clap parser.
#[derive(Debug, Clone, Default, Args)]
pub struct GlobalOptions {
    /// Output mode: auto, json, jsonl, text, plain.
    #[arg(long, value_enum, global = true, value_name = "MODE")]
    pub output: Option<OutputMode>,

    /// Emit a single JSON envelope.
    #[arg(long, global = true)]
    pub json: bool,

    /// Emit newline-delimited JSON envelopes.
    #[arg(long, global = true)]
    pub jsonl: bool,

    /// Emit simple text output.
    #[arg(long, global = true)]
    pub text: bool,

    /// Emit plain text output with no styling.
    #[arg(long, global = true)]
    pub plain: bool,

    /// Disable color.
    #[arg(long, global = true)]
    pub no_color: bool,

    /// Suppress non-essential human output.
    #[arg(short = 'q', long, global = true)]
    pub quiet: bool,

    /// Increase verbosity.
    #[arg(short = 'v', long, action = clap::ArgAction::Count, global = true)]
    pub verbose: u8,

    /// Show what would happen without side effects.
    #[arg(long, global = true)]
    pub dry_run: bool,

    /// Assume yes for confirmations.
    #[arg(short = 'y', long, global = true)]
    pub yes: bool,

    /// Emit command schema instead of running the command.
    #[arg(long, global = true)]
    pub schema: bool,

    /// Emit a complete machine-readable manifest for agents.
    #[arg(long, global = true)]
    pub agent_manifest: bool,

    /// Alias for --agent-manifest.
    #[arg(long, global = true)]
    pub help_agent: bool,
}

/// Resolve the effective output mode from flags, environment, and terminal state.
pub fn resolve_output_mode(options: &GlobalOptions) -> OutputMode {
    if options.json {
        return OutputMode::Json;
    }
    if options.jsonl {
        return OutputMode::Jsonl;
    }
    if options.text {
        return OutputMode::Text;
    }
    if options.plain {
        return OutputMode::Plain;
    }

    let mode = options
        .output
        .or_else(|| {
            env::var("TOOLI_OUTPUT")
                .ok()
                .and_then(|raw| raw.parse().ok())
        })
        .unwrap_or(OutputMode::Auto);

    match mode {
        OutputMode::Auto => {
            if env_flag_enabled("TOOLI_AGENT_MODE") || !io::stdout().is_terminal() {
                OutputMode::Json
            } else {
                OutputMode::Text
            }
        }
        other => other,
    }
}

pub(crate) fn no_color_requested(options: &GlobalOptions) -> bool {
    options.no_color || env::var_os("NO_COLOR").is_some()
}

pub(crate) fn caller_id_from_env() -> Option<String> {
    env::var("TOOLI_CALLER")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

pub(crate) fn env_flag_enabled(name: &str) -> bool {
    env::var(name)
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn explicit_json_wins() {
        let options = GlobalOptions {
            json: true,
            output: Some(OutputMode::Text),
            ..GlobalOptions::default()
        };

        assert_eq!(resolve_output_mode(&options), OutputMode::Json);
    }

    #[test]
    fn parses_output_modes() {
        assert_eq!("json".parse::<OutputMode>().unwrap(), OutputMode::Json);
        assert!("yaml".parse::<OutputMode>().is_err());
    }
}
