# Tooli Rust

A lean Rust crate for building agent-friendly CLI tools. Tooli sits on top of
`clap` and adds the parts most CLIs reinvent: stable JSON envelopes, structured
errors with categories and exit codes, JSON Schema export, agent-facing
metadata, and a non-interactive contract suitable for skills and automation.

## Quick Start

```bash
cargo run -p file_tools -- find '*.rs' --root crates/tooli/src
cargo run -p file_tools -- find '*.rs' --root crates/tooli/src --json
cargo run -p file_tools -- find --schema
cargo run -p file_tools -- read ./README.md --json
cargo run -p file_tools -- --agent-manifest
```

Run checks:

```bash
cargo fmt --all --check
cargo test --workspace
cargo clippy --workspace --all-targets --all-features -- -D warnings
```

## Crates

- `crates/tooli`: runtime, envelopes, errors, output modes, schema generation,
  metadata, agent manifest.
- `crates/tooli-macros`: `#[derive(TooliCli)]` proc macro for subcommand enums.
- `examples/file_tools`: example CLI showing the MVP integration pattern.

## Status

Version `0.1.0-alpha.3`. Implemented:

- typed `Command` trait with optional `HumanRender` override,
- `Dispatch` trait + `#[derive(TooliCli)]` macro for one-line subcommand wiring,
- `App::handle_pre_parse_intents` / `App::dispatch` runner,
- `GlobalOptions` for Tooli's global flags,
- `OutputMode` resolution via flags, environment, and terminal detection,
- success and error envelopes with stable shape,
- structured `ToolError` (categories, codes, retryability, fields, suggestions),
- JSON Schema export with cycle-bounded `$ref` inlining,
- annotation and capability metadata,
- optional capability enforcement through `TOOLI_ALLOWED_CAPABILITIES`,
- `InputSource` for file/stdin inputs,
- `SecretString` redacted in debug output, JSON, and schema,
- JSONL output for array results,
- confirmation gates for dangerous commands,
- `--agent-manifest` / `--help-agent` for complete machine-readable discovery,
- structured missing-command and parser errors in machine modes.

Not implemented yet:

- async command support,
- streaming JSONL (avoids `serde_json::Value` round-trip),
- MCP adapter,
- richer human rendering library (commands can `impl HumanRender` themselves).

## Minimal Pattern

Five lines of dispatch:

```rust
use tooli::prelude::*;

#[derive(Debug, Parser)]
struct Cli {
    #[command(flatten)]
    global: GlobalOptions,
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Debug, Subcommand, TooliCli)]
enum Commands {
    Find(FindArgs),
    Read(ReadArgs),
}

fn main() -> std::process::ExitCode {
    let app = App::new("file-tools")
        .version(env!("CARGO_PKG_VERSION"))
        .description("Find and read files.");

    if let Some(exit) = app.handle_pre_parse_intents::<Commands>() {
        return exit;
    }
    let cli = match Cli::try_parse() {
        Ok(cli) => cli,
        Err(err) => return app.exit_for_clap_error(err),
    };
    app.dispatch::<Commands>(&cli.global, cli.command)
}
```

`#[derive(TooliCli)]` generates the `Dispatch` impl: it provides the list of
subcommand names, dispatches each variant to `App::run_command`, dispatches
`<command> --schema` requests, and supplies the schemas embedded in
`--agent-manifest`. Variant names are kebab-cased (`FindFiles` → `find-files`)
and can be overridden with `#[tooli(name = "...")]`.

A command implementation looks like this:

```rust
#[derive(Debug, Args, JsonSchema)]
struct FindArgs {
    pattern: String,
    #[arg(long, default_value = ".")]
    root: String,
}

#[derive(Debug, Serialize, JsonSchema)]
struct FileHit {
    path: String,
    size: u64,
}

impl Command for FindArgs {
    type Output = Vec<FileHit>;

    fn meta() -> CommandMeta {
        CommandMeta::new()
            .description("Find files matching a glob.")
            .annotation(Annotation::ReadOnly)
            .capability("fs:read")
    }

    fn run(self, _ctx: Context) -> Result<Self::Output> { /* ... */ Ok(vec![]) }

    // Optional: override JSON-pretty-print fallback for `--text` / `--auto`.
    fn render_human(output: &Self::Output, w: &mut dyn std::io::Write) -> std::io::Result<()> {
        for hit in output { writeln!(w, "{}", hit.path)?; }
        Ok(())
    }
}
```

## JSON Naming Policy

Two conventions coexist on purpose to match the Python Tooli contract:

- **snake_case** for envelope and error fields (`duration_ms`, `dry_run`,
  `is_retryable`, `caller_id`).
- **camelCase** for schema/metadata hints, for MCP compatibility (`inputSchema`,
  `outputSchema`, `readOnlyHint`, `requiresConfirmation`).

The agent manifest reports `schema_version: "1.0"` (string) so additive
changes don't burn the major.

## Agent Contract

Tooli Rust CLIs should be fully non-interactive:

- every operation expressible with command-line arguments or stdin,
- every command supports `--schema`,
- the whole CLI supports `--agent-manifest`,
- agents use `--json` or `--jsonl` for execution,
- destructive commands require `--dry-run` or `--yes`,
- no command forces a prompt, pager, editor, or TUI.

See `ADOPTION.md` for migration guidance from a plain `clap` CLI.
