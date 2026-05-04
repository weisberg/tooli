use schemars::JsonSchema;
use serde::Serialize;
use serde_json::{json, Value};
use std::process::ExitCode;
use tooli::{
    capabilities_allowed, command_schema, AgentManifest, Annotation, AnnotationSet, Command,
    CommandMeta, Context, EnvelopeMeta, ErrorCategory, ErrorEnvelope, Example, GlobalOptions,
    InputSource, OutputMode, Result, SecretString, SuccessEnvelope, Suggestion, ToolError,
    SCHEMA_VERSION,
};

#[derive(Debug, JsonSchema)]
struct SearchArgs {
    /// Search query.
    query: String,
    /// Maximum number of rows.
    #[schemars(default = "default_limit")]
    limit: usize,
}

#[derive(Debug, Serialize, JsonSchema)]
struct SearchRow {
    id: u64,
    title: String,
}

#[derive(Debug, JsonSchema)]
struct DangerousArgs;

#[derive(Debug, Serialize, JsonSchema)]
struct DangerousResult {
    executed: bool,
}

fn default_limit() -> usize {
    10
}

impl Command for SearchArgs {
    type Output = Vec<SearchRow>;

    fn meta() -> CommandMeta {
        CommandMeta::new()
            .description("Search rows.")
            .annotation(Annotation::ReadOnly)
            .annotation(Annotation::Idempotent)
            .capability("db:read")
            .example_with_description("search rust --limit 5", "Search for Rust rows.")
    }

    fn run(self, _ctx: Context) -> Result<Self::Output> {
        Ok(vec![SearchRow {
            id: 1,
            title: format!("{}:{}", self.query, self.limit),
        }])
    }
}

impl Command for DangerousArgs {
    type Output = DangerousResult;

    fn meta() -> CommandMeta {
        CommandMeta::new()
            .description("Dangerous command.")
            .annotation(Annotation::Destructive)
            .requires_confirmation()
    }

    fn run(self, _ctx: Context) -> Result<Self::Output> {
        Ok(DangerousResult { executed: true })
    }
}

#[test]
fn success_envelope_serializes_stable_shape() {
    let result = vec![SearchRow {
        id: 7,
        title: "tooli".to_string(),
    }];
    let meta = EnvelopeMeta::new("search.rows", "0.1.0", 12)
        .dry_run(true)
        .caller_id(Some("codex".to_string()));
    let envelope = SuccessEnvelope::new(&result, meta);
    let payload = serde_json::to_value(envelope).expect("envelope should serialize");

    assert_eq!(payload["ok"], true);
    assert_eq!(payload["result"][0]["id"], 7);
    assert_eq!(payload["meta"]["tool"], "search.rows");
    assert_eq!(payload["meta"]["version"], "0.1.0");
    assert_eq!(payload["meta"]["duration_ms"], 12);
    assert_eq!(payload["meta"]["dry_run"], true);
    assert_eq!(payload["meta"]["caller_id"], "codex");
}

#[test]
fn error_envelope_serializes_retry_guidance_and_details() {
    let error = ToolError::input("invalid query")
        .code("E1007")
        .field("query")
        .retryable(true)
        .suggestion(
            Suggestion::retry("Use a non-empty query.", "search rust")
                .applicability("when query is empty"),
        )
        .detail("received", json!(""));
    let envelope = ErrorEnvelope::new(error, EnvelopeMeta::new("search.rows", "0.1.0", 4));
    let payload = serde_json::to_value(envelope).expect("envelope should serialize");

    assert_eq!(payload["ok"], false);
    assert_eq!(payload["result"], Value::Null);
    assert_eq!(payload["error"]["code"], "E1007");
    assert_eq!(payload["error"]["category"], "input");
    assert_eq!(payload["error"]["field"], "query");
    assert_eq!(payload["error"]["is_retryable"], true);
    assert_eq!(
        payload["error"]["suggestion"]["action"],
        "retry_with_modified_input"
    );
    assert_eq!(payload["error"]["details"]["received"], "");
}

#[test]
fn all_error_categories_have_default_codes_and_exit_codes() {
    let cases = [
        (ToolError::input("input"), "E1000", ErrorCategory::Input, 2),
        (ToolError::auth("auth"), "E2000", ErrorCategory::Auth, 30),
        (ToolError::state("state"), "E3000", ErrorCategory::State, 10),
        (
            ToolError::runtime("runtime"),
            "E4000",
            ErrorCategory::Runtime,
            70,
        ),
        (
            ToolError::internal("internal"),
            "E5000",
            ErrorCategory::Internal,
            70,
        ),
    ];

    for (error, code, category, exit_code) in cases {
        assert_eq!(error.code, code);
        assert_eq!(error.category, category);
        assert_eq!(error.exit_code(), exit_code);
    }
}

#[test]
fn output_mode_resolution_obeys_explicit_flags() {
    assert_eq!(
        tooli::resolve_output_mode(&GlobalOptions {
            json: true,
            text: true,
            ..GlobalOptions::default()
        }),
        OutputMode::Json
    );
    assert_eq!(
        tooli::resolve_output_mode(&GlobalOptions {
            jsonl: true,
            ..GlobalOptions::default()
        }),
        OutputMode::Jsonl
    );
    assert_eq!(
        tooli::resolve_output_mode(&GlobalOptions {
            plain: true,
            output: Some(OutputMode::Json),
            ..GlobalOptions::default()
        }),
        OutputMode::Plain
    );
}

#[test]
fn annotation_and_metadata_builders_are_serialization_friendly() {
    let annotations = AnnotationSet::default()
        .with(Annotation::ReadOnly)
        .with(Annotation::OpenWorld);
    let meta = CommandMeta::new()
        .description("Read from a public API.")
        .annotation(Annotation::ReadOnly)
        .annotation(Annotation::OpenWorld)
        .capability("net:read")
        .example("fetch --id 123")
        .deprecated("Use fetch-v2 instead.");
    let payload = serde_json::to_value(meta).expect("metadata should serialize");

    assert!(annotations.read_only);
    assert!(annotations.open_world);
    assert_eq!(payload["description"], "Read from a public API.");
    assert_eq!(payload["annotations"]["readOnlyHint"], true);
    assert_eq!(payload["annotations"]["openWorldHint"], true);
    assert_eq!(payload["capabilities"][0], "net:read");
    assert_eq!(payload["examples"][0]["command"], "fetch --id 123");
    assert_eq!(payload["deprecated"], true);
    assert_eq!(payload["deprecated_message"], "Use fetch-v2 instead.");
}

#[test]
fn examples_can_include_optional_descriptions() {
    let bare = Example::new("search rust");
    let described = Example::new("search rust").description("Search Rust rows.");
    let bare_payload = serde_json::to_value(bare).expect("example should serialize");
    let described_payload = serde_json::to_value(described).expect("example should serialize");

    assert_eq!(bare_payload["command"], "search rust");
    assert!(bare_payload.get("description").is_none());
    assert_eq!(described_payload["description"], "Search Rust rows.");
}

#[test]
fn command_schema_contains_input_output_and_agent_metadata() {
    let schema = command_schema::<SearchArgs>("search");
    let payload = serde_json::to_value(schema).expect("schema should serialize");

    assert_eq!(payload["name"], "search");
    assert_eq!(payload["description"], "Search rows.");
    assert_eq!(payload["annotations"]["readOnlyHint"], true);
    assert_eq!(payload["annotations"]["idempotentHint"], true);
    assert_eq!(payload["capabilities"][0], "db:read");
    assert_eq!(payload["examples"][0]["command"], "search rust --limit 5");
    assert_eq!(
        payload["inputSchema"]["properties"]["query"]["type"],
        "string"
    );
    assert_eq!(payload["inputSchema"]["properties"]["limit"]["default"], 10);
    assert_eq!(payload["outputSchema"]["type"], "array");

    let rendered = serde_json::to_string(&payload).expect("schema should render");
    assert!(!rendered.contains("\"$ref\""));
    assert!(!rendered.contains("\"definitions\""));
}

#[test]
fn command_schema_includes_confirmation_metadata() {
    let schema = command_schema::<DangerousArgs>("danger");
    let payload = serde_json::to_value(schema).expect("schema should serialize");

    assert_eq!(payload["requiresConfirmation"], true);
    assert_eq!(payload["annotations"]["destructiveHint"], true);
}

#[test]
fn app_blocks_confirmation_required_commands_without_yes_or_dry_run() {
    let app = tooli::App::new("danger-test").version("0.1.0");
    let options = GlobalOptions {
        json: true,
        ..GlobalOptions::default()
    };

    let exit = app.run_command("danger", DangerousArgs, &options);

    assert_eq!(exit, ExitCode::from(2));
}

#[test]
fn app_allows_confirmation_required_commands_with_yes() {
    let app = tooli::App::new("danger-test").version("0.1.0");
    let options = GlobalOptions {
        json: true,
        yes: true,
        ..GlobalOptions::default()
    };

    let exit = app.run_command("danger", DangerousArgs, &options);

    assert_eq!(exit, ExitCode::SUCCESS);
}

#[test]
fn capabilities_are_open_when_env_is_unset_or_empty() {
    std::env::remove_var("TOOLI_ALLOWED_CAPABILITIES");
    assert!(capabilities_allowed(&["fs:read".to_string()]));

    std::env::set_var("TOOLI_ALLOWED_CAPABILITIES", "");
    assert!(capabilities_allowed(&["fs:read".to_string()]));
    std::env::remove_var("TOOLI_ALLOWED_CAPABILITIES");
}

#[test]
fn input_source_and_secret_types_have_agent_safe_schema_and_serialization() {
    let input_schema = serde_json::to_value(schemars::schema_for!(InputSource))
        .expect("input schema should serialize");
    let secret_schema = serde_json::to_value(schemars::schema_for!(SecretString))
        .expect("secret schema should serialize");
    let secret = SecretString::new("top-secret");

    assert_eq!(input_schema["type"], "string");
    assert!(input_schema["description"]
        .as_str()
        .is_some_and(|description| description.contains("stdin")));
    assert_eq!(secret_schema["type"], "string");
    assert_eq!(secret_schema["format"], "password");
    assert_eq!(secret.expose_secret(), "top-secret");
    assert_eq!(serde_json::to_value(secret).unwrap(), json!("[REDACTED]"));
}

#[test]
fn agent_manifest_describes_noninteractive_cli_contract() {
    let manifest = AgentManifest::new(
        "search-tool",
        "0.1.0",
        vec![command_schema::<SearchArgs>("search")],
    )
    .description("Search rows.");
    let payload = serde_json::to_value(manifest).expect("manifest should serialize");

    assert_eq!(payload["schema_version"], SCHEMA_VERSION);
    assert_eq!(payload["schema_version"], "1.0");
    assert_eq!(payload["name"], "search-tool");
    assert_eq!(payload["non_interactive"], true);
    assert_eq!(payload["commands"][0]["name"], "search");
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
fn intent_detection_unifies_schema_manifest_and_run() {
    use tooli::Intent;
    assert_eq!(
        tooli::detect_intent_from_args(["--agent-manifest"], &["find"]),
        Intent::AgentManifest
    );
    assert_eq!(
        tooli::detect_intent_from_args(["--json", "find", "--schema"], &["find", "read"]),
        Intent::Schema("find")
    );
    assert_eq!(
        tooli::detect_intent_from_args(["find", "*.rs"], &["find"]),
        Intent::Run
    );
}
