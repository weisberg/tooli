//! Agent manifest — the root machine-readable description of a Tooli CLI.

use crate::CommandSchema;
use serde::Serialize;

/// The current manifest schema version. String-valued so additive changes can
/// bump the minor without breaking parsers that pin a major.
pub const SCHEMA_VERSION: &str = "1.0";

/// CLI flag documentation for agent manifests.
#[derive(Debug, Clone, Serialize)]
pub struct GlobalFlag {
    pub name: String,
    pub description: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub values: Vec<String>,
}

impl GlobalFlag {
    pub fn new(name: impl Into<String>, description: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            description: description.into(),
            values: Vec::new(),
        }
    }

    pub fn values(mut self, values: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.values = values.into_iter().map(Into::into).collect();
        self
    }
}

/// Skill-authoring instructions embedded in an agent manifest.
#[derive(Debug, Clone, Serialize)]
pub struct SkillGuide {
    pub summary: String,
    pub discovery_command: String,
    pub schema_command_pattern: String,
    pub invocation_pattern: String,
    pub rules: Vec<String>,
}

/// Complete machine-readable description of a Tooli CLI for agents.
#[derive(Debug, Clone, Serialize)]
pub struct AgentManifest {
    pub schema_version: &'static str,
    pub name: String,
    pub version: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    pub non_interactive: bool,
    pub commands: Vec<CommandSchema>,
    pub global_flags: Vec<GlobalFlag>,
    pub environment: Vec<GlobalFlag>,
    pub skill: SkillGuide,
}

impl AgentManifest {
    pub fn new(
        name: impl Into<String>,
        version: impl Into<String>,
        commands: Vec<CommandSchema>,
    ) -> Self {
        let name = name.into();
        Self {
            schema_version: SCHEMA_VERSION,
            version: version.into(),
            description: None,
            non_interactive: true,
            global_flags: default_global_flags(),
            environment: default_environment(),
            skill: default_skill_guide(&name),
            name,
            commands,
        }
    }

    pub fn description(mut self, description: impl Into<String>) -> Self {
        self.description = Some(description.into());
        self
    }
}

fn default_global_flags() -> Vec<GlobalFlag> {
    vec![
        GlobalFlag::new("--json", "Emit a single JSON Tooli envelope."),
        GlobalFlag::new("--jsonl", "Emit one JSON Tooli envelope per result item."),
        GlobalFlag::new("--output <MODE>", "Choose output mode.")
            .values(["auto", "json", "jsonl", "text", "plain"]),
        GlobalFlag::new(
            "--schema",
            "Emit this command's JSON schema and do not execute it.",
        ),
        GlobalFlag::new(
            "--agent-manifest",
            "Emit the complete machine-readable manifest for this CLI.",
        ),
        GlobalFlag::new("--help-agent", "Alias for --agent-manifest."),
        GlobalFlag::new(
            "--dry-run",
            "Preview command behavior without side effects.",
        ),
        GlobalFlag::new(
            "--yes",
            "Confirm commands that require explicit confirmation.",
        ),
        GlobalFlag::new("--no-color", "Disable color in human output."),
        GlobalFlag::new("--quiet", "Suppress non-essential human output."),
        GlobalFlag::new("--verbose", "Increase diagnostic verbosity."),
    ]
}

fn default_environment() -> Vec<GlobalFlag> {
    vec![
        GlobalFlag::new("TOOLI_OUTPUT", "Default output mode.").values([
            "auto", "json", "jsonl", "text", "plain",
        ]),
        GlobalFlag::new(
            "TOOLI_AGENT_MODE",
            "When truthy, auto output resolves to machine-readable JSON.",
        ),
        GlobalFlag::new("TOOLI_CALLER", "Caller identifier included in envelope metadata."),
        GlobalFlag::new(
            "TOOLI_ALLOWED_CAPABILITIES",
            "Comma or whitespace separated capability allow-list. Supports '*', exact matches, and namespace wildcards like 'fs:*'.",
        ),
        GlobalFlag::new("NO_COLOR", "Disable color in human output."),
    ]
}

fn default_skill_guide(name: &str) -> SkillGuide {
    SkillGuide {
        summary: format!(
            "Use `{name} --agent-manifest` to discover commands, then call concrete commands with `--json` or `--jsonl`. No interactive flow is required."
        ),
        discovery_command: format!("{name} --agent-manifest"),
        schema_command_pattern: format!("{name} <command> --schema"),
        invocation_pattern: format!("{name} <command> [args] --json"),
        rules: vec![
            "Never rely on interactive prompts; every operation must be expressed as CLI arguments or stdin.".to_string(),
            "Use --schema before invoking an unfamiliar command.".to_string(),
            "Use --json for single responses and --jsonl for list/stream responses.".to_string(),
            "Read `error.category`, `error.field`, `error.suggestion`, and exit code before retrying.".to_string(),
            "For destructive commands, use --dry-run first, then --yes only when policy allows.".to_string(),
            "Respect command capabilities and TOOLI_ALLOWED_CAPABILITIES policy failures.".to_string(),
        ],
    }
}
