# Adopting Tooli Rust

Use Tooli Rust on top of `clap` when a Rust CLI must serve both humans and
automation.

Use Tooli Rust when a tool needs any of:

- stable JSON output for agents or scripts,
- structured errors with machine-readable categories and exit codes,
- `--schema` for per-command discovery,
- `--agent-manifest` for whole-CLI discovery,
- JSONL output for list results,
- explicit read/write/destructive metadata,
- capability policy through `TOOLI_ALLOWED_CAPABILITIES`,
- safe handling for file/stdin inputs and secret strings.

Use plain `clap` alone when the tool is intentionally human-only and does not
need a machine contract.

## Migration From A `clap` CLI

1. Keep existing `#[derive(Parser)]`, `#[derive(Subcommand)]`, and
   `#[derive(Args)]` types.
2. Add `#[derive(JsonSchema)]` to argument and output types.
3. Add `#[command(flatten)] global: GlobalOptions` to the root parser.
4. Add `#[derive(TooliCli)]` to the subcommand enum.
5. Implement `Command` for each command argument type.
6. Replace `main()`'s subcommand `match` with two lines:

```rust
fn main() -> std::process::ExitCode {
    let app = App::new("my-tool")
        .version(env!("CARGO_PKG_VERSION"))
        .description("My agent-ready CLI.");

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

The runner handles the schema/manifest pre-parse, parser-error JSON, missing-
command structured errors, and per-variant dispatch. There is no longer a
hand-maintained list of subcommand name strings.

## Policy

Capability enforcement is opt-in. If `TOOLI_ALLOWED_CAPABILITIES` is unset or
empty, commands run normally. If set, each command capability must be allowed
by exact match, `*`, or a namespace wildcard:

```bash
TOOLI_ALLOWED_CAPABILITIES=fs:read my-tool count ./README.md --json
TOOLI_ALLOWED_CAPABILITIES=fs:* my-tool count ./README.md --json
```

Destructive commands can require explicit confirmation:

```rust
fn meta() -> CommandMeta {
    CommandMeta::new()
        .annotation(Annotation::Destructive)
        .requires_confirmation()
}
```

The runtime blocks those commands unless the user passes `--yes` or `--dry-run`.

## Customizing Human Output

`Command::render_human` defaults to pretty-printed JSON. Override it to emit
something a person would actually want to see:

```rust
impl Command for FindArgs {
    fn render_human(output: &Self::Output, w: &mut dyn std::io::Write) -> std::io::Result<()> {
        for hit in output { writeln!(w, "{}", hit.path)?; }
        Ok(())
    }
}
```

This affects only `--text`, `--plain`, and the `Auto` mode on a TTY. Machine
modes (`--json`, `--jsonl`, agent mode) are unaffected.

## Current Limits

- no async command trait yet,
- no MCP adapter yet,
- JSONL still materializes the result before splitting (true streaming is
  future work),
- no built-in human formatters beyond pretty-printed JSON.
