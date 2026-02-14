# Tooli Implementation Plan

This document defines the implementation roadmap for Tooli as a sequence of GitHub issues. Each issue is scoped to be independently implementable and reviewable. Issues within a phase are ordered by dependency — later issues may depend on earlier ones.

See [PRD.md](PRD.md) for full product requirements.

---

## Phase 1: Core Foundation (MVP)

The goal of Phase 1 is a working `Tooli` class that produces CLI commands with dual-mode output (human/machine), structured errors, and basic documentation generation. At the end of this phase, a developer can write a Tooli command and use it from a terminal or pipe its JSON output to another tool.

---

### Issue #1: Project scaffolding and dependency setup [DONE]

**Labels:** `phase-1`, `infrastructure`

Set up the project for real development: modern pyproject.toml with dependencies, test infrastructure, CI, and package structure.

**Acceptance criteria:**
- [x] Update `pyproject.toml`: bump to Python `>=3.10`, add dependencies (`typer>=0.9`, `pydantic>=2.0`, `rich>=13.0`), add optional `[dev]` extras (`pytest`, `pytest-cov`, `ruff`, `mypy`)
- [x] Create package structure: `tooli/`, `tooli/py.typed`, `tests/`, `tests/conftest.py`
- [x] Add `ruff.toml` with baseline lint/format config
- [x] Add `mypy.ini` or pyproject section for type checking
- [x] Add GitHub Actions CI workflow: lint, type-check, test on Python 3.10/3.11/3.12
- [x] Add `.gitignore` for Python projects
- [x] Verify `pip install -e ".[dev]"` works and `pytest` runs (even if no tests yet)

**Why first:** Everything else depends on a working dev environment.

---

### Issue #2: `Tooli` core class — subclass Typer with command registration [DONE]

**Labels:** `phase-1`, `core`

Create the `Tooli` class that subclasses `typer.Typer` and serves as the entry point for all Tooli functionality. At this stage it should be a thin wrapper that passes through to Typer — the extension points come in later issues.

**Acceptance criteria:**
- [x] `tooli/app.py`: `Tooli` class extending `typer.Typer`
- [x] Constructor accepts Tooli-specific kwargs (`default_output`, `mcp_transport`, `skill_auto_generate`, `permissions`) and stores them, passing standard kwargs through to `Typer.__init__`
- [x] `@app.command()` works identically to Typer's `@app.command()` for basic usage (no agent-specific metadata yet)
- [x] Export `Tooli` from `tooli/__init__.py`
- [x] Re-export `Annotated`, `Option`, `Argument` from `tooli/__init__.py` for convenience
- [x] Tests: a minimal Tooli app can be invoked via `CliRunner` and produces expected CLI output

**Depends on:** #1

---

### Issue #3: Output mode detection and `--output` global flag [DONE]

**Labels:** `phase-1`, `core`, `output`

Implement the output mode system: TTY auto-detection, the `--output` flag, and convenience aliases (`--json`, `--jsonl`, `--plain`, `--text`).

**Acceptance criteria:**
- [x] `tooli/output.py`: `OutputMode` enum (`AUTO`, `JSON`, `JSONL`, `TEXT`, `PLAIN`)
- [x] `tooli/output.py`: `resolve_output_mode(ctx)` function — checks explicit flag, then TTY detection, then `TOOLI_OUTPUT` env var
- [x] Global callback on `Tooli` that injects `--output` / `-o` and alias flags (`--json`, `--jsonl`, `--text`, `--plain`) into every command
- [x] Store resolved output mode in Click context (`ctx.obj` or `ctx.meta`)
- [x] If multiple output flags are provided, last one wins
- [x] `--no-color` flag + respect `NO_COLOR` env var (disable Rich markup)
- [x] Tests: verify auto-detection (TTY vs piped), explicit flags, env var override, alias flags, and last-wins behavior

**Depends on:** #2

---

### Issue #4: Return value capture and output routing [DONE]

**Labels:** `phase-1`, `core`, `output`

Override command invocation so that return values from command functions are captured and routed through the output system instead of being discarded (standard Typer behavior).

**Acceptance criteria:**
- [x] `tooli/command.py`: `TooliCommand` subclass of `TyperCommand` with custom `invoke()` that captures the return value
- [x] Wire `Tooli` to use `TooliCommand` as its default command class via the `cls` parameter
- [x] Output routing based on resolved `OutputMode`:
  - `HUMAN` / `AUTO` (TTY): print return value using `rich.print` (or `repr` fallback)
  - `JSON`: serialize return value as JSON to stdout
  - `JSONL`: one JSON object per line for list return values; single JSON line for scalar
  - `TEXT`: `str()` representation, no color
  - `PLAIN`: same as TEXT (alias)
- [x] If the command function returns `None`, emit nothing (preserve standard Typer behavior)
- [x] Tests: command returning `dict`, `list[dict]`, `str`, `int`, and `None` — verify correct output in each mode

**Depends on:** #3

---

### Issue #5: Output envelope (`ok` / `result` / `meta` wrapper) [DONE]

**Labels:** `phase-1`, `core`, `output`

Wrap JSON output in the standard envelope defined in the PRD.

**Acceptance criteria:**
- [x] `tooli/envelope.py`: `Envelope` Pydantic model with `ok: bool`, `result: Any`, `meta: EnvelopeMeta`
- [x] `EnvelopeMeta` model with `tool: str`, `version: str`, `duration_ms: int`, `warnings: list[str]`
- [x] In JSON/JSONL output modes, wrap the return value in the envelope before serialization
- [x] Capture command duration (wall-clock time around `invoke()`) and populate `duration_ms`
- [x] Populate `tool` from the app name + command name (e.g., `"file-tools.find-files"`)
- [x] Populate `version` from `Tooli.version` (or `"0.0.0"` if not set)
- [x] Tests: verify envelope structure, duration is plausible, tool/version are correct

**Depends on:** #4

---

### Issue #6: Global flags — `--quiet`, `--verbose`, `--dry-run`, `--yes`, `--timeout` [DONE]

**Labels:** `phase-1`, `core`

Add the remaining standard global flags to every command.

**Acceptance criteria:**
- [x] Extend the global callback from Issue #3 to inject: `--quiet` / `-q`, `--verbose` / `-v` (stackable count), `--dry-run`, `--yes`, `--timeout` (float, seconds)
- [x] Store all flag values in a `ToolContext` dataclass accessible via `ctx.obj`
- [x] `--quiet`: suppress Rich output formatting (emit only raw result in human mode)
- [x] `--verbose`: integer verbosity level (0 default, increments with each `-v`)
- [x] `--timeout`: if set, wrap command execution in a timeout (raise `ToolError` on expiry)
- [x] `--dry-run`: store flag; commands check `ctx.obj.dry_run` to skip side effects (framework does not enforce, just provides the flag)
- [x] `--yes`: skip interactive confirmation prompts; if stdin is not a TTY and `--yes` is not set, raise `InputError` instead of hanging
- [x] Tests: verify flag parsing, stacking `-vvv`, timeout expiry raises structured error, `--yes` skips prompts

**Depends on:** #3

---

### Issue #7: `ToolError` exception hierarchy and structured error output [DONE]

**Labels:** `phase-1`, `core`, `errors`

Implement the structured error system so that errors produce actionable JSON for agents.

**Acceptance criteria:**
- [x] `tooli/errors.py`: `ToolError` base exception with fields: `code: str`, `category: ErrorCategory`, `message: str`, `suggestion: Suggestion | None`, `is_retryable: bool`, `details: dict | None`
- [x] `ErrorCategory` enum: `INPUT`, `AUTH`, `STATE`, `RUNTIME`, `INTERNAL`
- [x] Subclasses: `InputError` (E1xxx), `AuthError` (E2xxx), `StateError` (E3xxx), `RuntimeError` (E4xxx), `InternalError` (E5xxx)
- [x] `Suggestion` dataclass: `action`, `fix`, `example`, `applicability`
- [x] In `TooliCommand.invoke()`, catch `ToolError` and route through output:
  - JSON mode: emit `{"ok": false, "error": {...}, "meta": {...}}` envelope to stdout
  - Text/human mode: emit formatted error to stderr
- [x] Map `ErrorCategory` to exit codes per the PRD taxonomy (INPUT→2, STATE→10, AUTH→30, RUNTIME→70, INTERNAL→70)
- [x] Catch unexpected exceptions and wrap them as `InternalError` with the traceback in `details` (only in verbose mode)
- [x] Tests: raise each error type, verify JSON envelope shape, verify exit codes, verify suggestion fields serialize correctly

**Depends on:** #5

---

### Issue #8: Exit code taxonomy [DONE]

**Labels:** `phase-1`, `core`, `errors`

Formalize the exit code mapping and ensure all command exits use the correct codes.

**Acceptance criteria:**
- [x] `tooli/exit_codes.py`: `ExitCode` enum with all codes from PRD (0, 2, 10, 20, 30, 40, 50, 65, 70, 75, 101)
- [x] `ToolError` subclasses map to the correct exit code by default, with override capability
- [x] `TooliCommand.invoke()` catches `SystemExit`, `ToolError`, and `click.exceptions` and maps them to the correct exit code
- [x] Click's `UsageError` maps to exit code 2
- [x] Tests: verify each error category produces the expected exit code

**Depends on:** #7

---

### Issue #9: `StdinOr[T]` input unification type [DONE]

**Labels:** `phase-1`, `core`, `input`

Implement the SmartInput system so commands can accept files, stdin, or URLs through a single parameter type.

**Acceptance criteria:**
- [x] `tooli/input.py`: `StdinOr` generic type that resolves input source
- [x] Resolution logic:
  - Explicit path string → open file
  - `-` → read from `sys.stdin`
  - URL pattern (`http://`, `https://`) → fetch via `urllib` (no extra dependency)
  - No argument + stdin is piped → read from stdin
  - No argument + stdin is TTY → raise `InputError` with helpful message
- [x] Return a file-like object or string content (configurable via type parameter)
- [x] Implement as a custom Click `ParamType` so it integrates with Typer's argument parsing
- [x] Tests: file input, stdin pipe, `-` argument, URL (mocked), missing input error

**Depends on:** #7

---

### Issue #10: Schema generation pipeline [DONE]

**Labels:** `phase-1`, `core`, `schema`

Generate JSON Schema from command function signatures, compatible with MCP `inputSchema`.

**Acceptance criteria:**
- [x] `tooli/schema.py`: `generate_tool_schema(func, command_info) -> ToolSchema` function
- [x] Build dynamic Pydantic model from `inspect.signature()` — map parameters to Pydantic fields with descriptions from `Option`/`Argument` help text
- [x] Type mapping per PRD: `str`, `int`, `float`, `bool`, `Path`, `Enum`, `list[T]`, `Optional[T]`, `Literal`, Pydantic `BaseModel`
- [x] `$ref` dereferencing: inline all `$ref` entries in generated JSON Schema for broad client compatibility
- [x] `ToolSchema` model: `name`, `description`, `input_schema`, `output_schema` (optional), `annotations`, `examples`
- [x] Skip injected/framework parameters (context objects, output mode, etc.) from the schema
- [x] Tests: generate schemas for functions with various type signatures, verify JSON Schema validity, verify `$ref` inlining

**Depends on:** #2

---

### Issue #11: `--schema` flag for per-command and app-level schema export [DONE]

**Labels:** `phase-1`, `core`, `schema`

Wire schema generation into the CLI so users and agents can introspect commands.

**Acceptance criteria:**
- [x] Add `--schema` global flag: when present, print the JSON Schema for the current command and exit (do not execute the command)
- [x] At app level (`mytool --schema`), output schemas for all registered commands as a JSON array
- [x] At command level (`mytool find-files --schema`), output schema for that single command
- [x] Schema output includes `inputSchema`, `description`, `annotations`, and `examples` if defined
- [x] Tests: verify `--schema` output matches expected JSON Schema structure for a sample command

**Depends on:** #10, #6

---

### Issue #12: Command metadata — behavioral annotations, examples, error codes [DONE]

**Labels:** `phase-1`, `core`

Extend the `@app.command()` decorator to accept agent-specific metadata.

**Acceptance criteria:**
- [x] `tooli/annotations.py`: `ReadOnly`, `Idempotent`, `Destructive`, `OpenWorld` annotation objects that can be combined with `|` operator
- [x] `@app.command()` accepts: `annotations`, `examples`, `error_codes`, `timeout`, `cost_hint`, `human_in_the_loop`, `auth`
- [x] Store metadata on the command object (accessible for schema generation, SKILL.md, MCP export)
- [x] Annotations map to MCP-compatible hints: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`
- [x] `examples` stored as structured data (args + description)
- [x] Tests: define commands with various metadata combinations, verify metadata is accessible and correctly stored

**Depends on:** #2

---

### Issue #13: Basic SKILL.md generation [DONE]

**Labels:** `phase-1`, `docs`

Auto-generate a SKILL.md file from app introspection.

**Acceptance criteria:**
- [x] `tooli/docs/skill.py`: `generate_skill_md(app: Tooli) -> str` function
- [x] Built-in `generate-skill` command registered on `Tooli`
- [x] Generated SKILL.md includes:
  - Tool name and description (from app metadata)
  - Command list with synopsis
  - Per-command: description, parameters (name, type, default, help), examples
  - Behavioral annotations (read-only, destructive, idempotent)
  - Exit code reference
- [x] Docstring parsing: extract descriptions from Google, NumPy, or Sphinx-style docstrings
- [x] Output is valid Markdown
- [x] Tests: generate SKILL.md for a multi-command app, verify structure and content accuracy

**Depends on:** #10, #12

---

### Issue #14: Built-in contract tests and test utilities [DONE]

**Labels:** `phase-1`, `testing`

Provide test utilities that Tooli app developers can use to verify their tool contracts don't break.

**Acceptance criteria:**
- [x] `tooli/testing.py`: `TooliTestClient` wrapping Typer's `CliRunner` with convenience methods
- [x] `assert_json_envelope(result)`: verify output matches `{ok, result, meta}` shape
- [x] `assert_schema_stable(app, snapshot_path)`: compare current schema output against a saved snapshot (write snapshot on first run)
- [x] `assert_stdin_file_parity(app, command, file_input, stdin_input)`: run command with file and stdin, verify identical JSON output
- [x] `assert_exit_code(result, expected_code)`: verify exit code
- [x] Tests: use the utilities to test a sample app (meta-test: testing the test utilities)

**Depends on:** #7, #5

---

### Issue #15: Configuration precedence system [DONE]

**Labels:** `phase-1`, `core`

Implement the configuration precedence chain: flags > env > .env > project config > user config > system config > defaults.

**Acceptance criteria:**
- [x] `tooli/config.py`: `TooliConfig` class that resolves configuration values through the precedence chain
- [x] Support `TOOLI_*` environment variables (e.g., `TOOLI_OUTPUT=json`)
- [x] Load `.env` file from project root if present (use `python-dotenv` or manual parsing — decide based on dependency budget)
- [x] Load project config from `pyproject.toml` `[tool.tooli]` section
- [x] Load user config from `~/.config/tooli/config.yaml` (optional, skip if missing)
- [x] Integrate with `Tooli` — resolved config available at command execution time
- [x] Tests: verify precedence order with conflicting values at each level

**Depends on:** #6

---

## Phase 2: Agent Differentiation

Phase 2 makes Tooli a standout framework for agent tooling: MCP server generation, advanced schema features, response control, documentation formats, and the transform pipeline. At the end of this phase, a Tooli app can serve as an MCP server and generate comprehensive agent documentation.

---

### Issue #16: MCP tool definition export [DONE]

**Labels:** `phase-2`, `mcp`

Generate MCP-compatible tool definitions from registered commands.

**Acceptance criteria:**
- [x] `tooli/mcp/export.py`: `export_mcp_tools(app: Tooli) -> list[MCPToolDefinition]`
- [x] `MCPToolDefinition` model: `name`, `description`, `inputSchema`, `outputSchema` (optional), `annotations`
- [x] Map Tooli command metadata to MCP tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`)
- [x] Built-in `mcp export` subcommand that outputs tool definitions as JSON
- [x] Tests: export definitions for a multi-command app, verify MCP schema compliance

**Depends on:** #10, #12

---

### Issue #17: MCP stdio server mode [DONE]

**Labels:** `phase-2`, `mcp`

Serve a Tooli app as an MCP server over stdio transport.

**Acceptance criteria:**
- [x] `tooli/mcp/server.py`: MCP server implementation using `fastmcp` (optional dependency)
- [x] Built-in `mcp serve --transport stdio` subcommand
- [x] Each Tooli command becomes an MCP tool; invocation calls the command function directly (not via subprocess)
- [x] Return values are serialized as MCP `structuredContent`
- [x] `ToolError` exceptions become MCP error responses with `isError: true`
- [x] Strict stdout discipline: zero logging to stdout during MCP mode
- [x] Tests: spin up server, send MCP tool call, verify response structure

**Depends on:** #16

---

### Issue #18: MCP HTTP server mode

**Labels:** `phase-2`, `mcp`

Add HTTP transport option for the MCP server.

**Acceptance criteria:**
- [ ] `mcp serve --transport http --port 8080` starts an HTTP-based MCP server
- [ ] Uses `fastmcp` HTTP transport (or SSE, depending on fastmcp capabilities)
- [ ] Same tool surface as stdio mode
- [ ] Tests: start HTTP server, send tool call via HTTP, verify response

**Depends on:** #17

---

### Issue #19: Response verbosity control (`--response-format`) [DONE]

**Labels:** `phase-2`, `core`, `output`

Let commands emit concise or detailed responses, controlled by a standard flag.

**Acceptance criteria:**
- [x] Add `--response-format` global flag: `concise` (default) or `detailed`
- [x] Store in `ToolContext` so command functions can check it
- [x] `tooli/output.py`: `ResponseFormat` enum
- [x] Convention: `concise` returns minimal fields (IDs, names, status); `detailed` includes all fields, nested objects, timestamps
- [x] Document the convention; enforcement is per-command (framework provides the flag and context, not automatic truncation)
- [x] Tests: verify flag parsing, verify command function receives the correct format

**Depends on:** #6

---

### Issue #20: Pagination, filtering, and truncation primitives [DONE]

**Labels:** `phase-2`, `core`, `output`

Provide standard flags for controlling output volume on list-returning commands.

**Acceptance criteria:**
- [x] Global flags: `--limit` (int), `--cursor` (string), `--fields` / `--select` (comma-separated field names), `--filter` (key=value), `--max-items` (int)
- [x] `tooli/pagination.py`: `PaginationParams` dataclass populated from flags
- [x] When `--limit` is set and result is truncated, include `"next_cursor"` in `meta` and a `"truncated": true` field with guidance message
- [x] `--fields`: post-process JSON output to include only specified keys (top-level filtering)
- [x] These flags are opt-in per command via `@app.command(paginated=True)` to avoid cluttering simple commands
- [x] Tests: verify pagination metadata, field filtering, truncation guidance message

**Depends on:** #5

---

### Issue #21: `--help-agent` token-optimized help output [DONE]

**Labels:** `phase-2`, `core`

Provide a minified, token-efficient help format for agents.

**Acceptance criteria:**
- [x] Add `--help-agent` global flag
- [x] When set, output a dense schema-like representation: command signature, parameter types/defaults, constraints, description — no decorative formatting, no ASCII art, minimal whitespace
- [x] Format inspired by TypeScript interface notation (LLMs parse this efficiently)
- [x] Tests: verify `--help-agent` output is valid, compact, and contains all parameter information

**Depends on:** #10, #6

---

### Issue #22: Tool behavioral annotations in output and schema [DONE]

**Labels:** `phase-2`, `core`, `schema`

Surface behavioral annotations (read-only, destructive, idempotent, cost_hint) in all output channels.

**Acceptance criteria:**
- [x] `--schema` output includes `annotations` object with MCP-compatible hints
- [x] `--help` output shows a "Behavior" line (e.g., `[read-only, idempotent]`)
- [x] `--help-agent` output includes annotations
- [x] SKILL.md generation includes a "Governance" section per command with annotations + `cost_hint` + `human_in_the_loop`
- [x] JSON envelope `meta` includes `annotations` when present
- [x] Tests: verify annotations appear in each output channel

**Depends on:** #12, #13, #11

---

### Issue #23: llms.txt documentation generation

**Labels:** `phase-2`, `docs`

Generate llms.txt and llms-full.txt from app introspection.

**Acceptance criteria:**
- [ ] `tooli/docs/llms_txt.py`: `generate_llms_txt(app) -> str` and `generate_llms_full_txt(app) -> str`
- [ ] Built-in `docs llms` subcommand
- [ ] `llms.txt`: curated navigation — tool name, purpose, command list with one-line descriptions, links to full docs
- [ ] `llms-full.txt`: expanded docs — full parameter details, examples, error codes, schemas
- [ ] Follows the [llms.txt](https://llmstxt.org/) specification structure
- [ ] Tests: generate both files for a multi-command app, verify structure

**Depends on:** #13

---

### Issue #24: Unix man page generation

**Labels:** `phase-2`, `docs`

Generate man pages from command metadata.

**Acceptance criteria:**
- [ ] `tooli/docs/man.py`: `generate_man_page(app) -> str`
- [ ] Built-in `docs man` subcommand
- [ ] Output in standard man page format (roff/troff) or plain text with man-page conventions
- [ ] Includes: NAME, SYNOPSIS, DESCRIPTION, OPTIONS, EXIT CODES, EXAMPLES, SEE ALSO
- [ ] Content is consistent with `--help`, `--schema`, and SKILL.md
- [ ] Tests: generate man page, verify required sections are present

**Depends on:** #13

---

### Issue #25: Transform pipeline — namespacing and filtering

**Labels:** `phase-2`, `architecture`

Implement the transform layer that modifies tool surfaces before they're exposed.

**Acceptance criteria:**
- [ ] `tooli/transforms.py`: `Transform` base class with `apply(tools: list[ToolDef]) -> list[ToolDef]`
- [ ] `NamespaceTransform`: adds a prefix to tool names (e.g., `git_commit`, `fs_read`)
- [ ] `VisibilityTransform`: filters tools by tags (e.g., show only `agent`-tagged tools, hide `internal`-tagged)
- [ ] `Tooli.with_transforms(*transforms)` returns a new app view with transforms applied
- [ ] Transforms affect: MCP export, schema export, SKILL.md generation, `--help` output
- [ ] Tests: apply namespace + visibility transforms, verify tool names and filtering

**Depends on:** #16

---

### Issue #26: Null-delimited list processing (`--print0`, `--null`) [DONE]

**Labels:** `phase-2`, `core`, `input`

Support safe list processing with null delimiters for bash interop.

**Acceptance criteria:**
- [x] `--print0` global flag: when set, list-type outputs use `\0` delimiter instead of newlines (in TEXT/PLAIN modes)
- [x] `--null` global flag: when set, stdin list parsing uses `\0` delimiter
- [x] These flags are opt-in per command via `@app.command(list_processing=True)`
- [x] Tests: verify `--print0` output, verify `--null` input parsing, verify interop with `xargs -0`

**Depends on:** #9

---

### Issue #27: OpenAPI schema export and HTTP serve mode

**Labels:** `phase-2`, `api`

Generate OpenAPI schemas and optionally serve commands as an HTTP API.

**Acceptance criteria:**
- [ ] `tooli/api/openapi.py`: `generate_openapi_schema(app) -> dict` producing valid OpenAPI 3.1 spec
- [ ] Each command becomes a POST endpoint; parameters map to request body schema
- [ ] Response schema matches the output envelope
- [ ] Built-in `api export-openapi` subcommand
- [ ] Built-in `api serve --port 8000` subcommand using a lightweight ASGI server (e.g., uvicorn + Starlette, optional dependency)
- [ ] HTTP responses preserve envelope/error semantics from `--output json`
- [ ] Tests: verify OpenAPI schema validity, verify HTTP endpoint returns correct envelope

**Depends on:** #10, #5

---

### Issue #28: `--idempotency-key` support for safe retries [DONE]

**Labels:** `phase-2`, `core`

Add idempotency key support so agents can safely retry commands.

**Acceptance criteria:**
- [x] `--idempotency-key` global flag (string)
- [x] Store in `ToolContext`; command functions can check for duplicate keys
- [x] `tooli/idempotency.py`: simple file-based or in-memory cache for idempotency tracking within a process lifetime
- [x] If a duplicate key is detected and the command is marked `idempotent`, return the cached result
- [x] If not marked idempotent, return an error explaining the duplicate key
- [x] Tests: verify duplicate key returns cached result for idempotent commands, error for non-idempotent

**Depends on:** #12, #6

---

## Phase 3: Advanced Features

Phase 3 adds enterprise and ecosystem features: provider system, versioning, observability, policy, authorization, and the agent evaluation harness. These are individually valuable and mostly independent of each other.

---

### Issue #29: Provider system — local and filesystem providers

**Labels:** `phase-3`, `architecture`

Implement the provider abstraction for sourcing tools from multiple locations.

**Acceptance criteria:**
- [ ] `tooli/providers/base.py`: `Provider` abstract base class with `get_tools() -> list[ToolDef]`
- [ ] `tooli/providers/local.py`: `LocalProvider` — sources tools from `@app.command()` decorated functions (current default behavior)
- [ ] `tooli/providers/filesystem.py`: `FileSystemProvider` — loads tool modules from a directory path, with optional hot-reloading (via file watcher) for development
- [ ] `Tooli.add_provider(provider)` method to register additional providers
- [ ] Tests: register tools via both providers, verify they appear in schema/help/MCP export

**Depends on:** #25

---

### Issue #30: Tool versioning

**Labels:** `phase-3`, `core`

Support versioning of individual tools.

**Acceptance criteria:**
- [ ] `@app.command(version="1.0.0")` decorator argument
- [ ] Default behavior: expose the latest version of each tool
- [ ] `VersionFilter` transform: filter tools to a specific version range
- [ ] Schema export includes tool version
- [ ] Deprecation support: `@app.command(deprecated=True, deprecated_message="Use find-files-v2 instead")`
- [ ] Tests: register multiple versions of a tool, verify default latest, verify version filtering

**Depends on:** #25

---

### Issue #31: Dry-run mode framework support

**Labels:** `phase-3`, `core`

Elevate `--dry-run` from a simple flag to a framework-supported pattern.

**Acceptance criteria:**
- [ ] `tooli/dry_run.py`: `DryRunRecorder` context manager that captures planned actions
- [ ] Helper decorator `@dry_run_support` that automatically returns the action plan when `--dry-run` is active
- [ ] Action plan format: list of `{"action": "create_file", "target": "/path", "details": {...}}` objects
- [ ] In JSON mode, dry-run output uses the standard envelope with `"dry_run": true` in meta
- [ ] Tests: command with dry-run support returns action plan instead of executing

**Depends on:** #6

---

### Issue #32: Agent evaluation harness

**Labels:** `phase-3`, `observability`

Built-in tooling to record and analyze agent-tool interactions.

**Acceptance criteria:**
- [ ] `tooli/eval/recorder.py`: `InvocationRecorder` that logs each command invocation (command, args, result status, duration, error code) to a JSONL file
- [ ] Enable via `TOOLI_RECORD=path/to/log.jsonl` env var or `Tooli(record=True)`
- [ ] `tooli/eval/analyzer.py`: `analyze_invocations(log_path)` that reports:
  - Total invocations per command
  - Invalid parameter rate per command
  - Most common error codes
  - Redundant/duplicate invocations
  - Average duration per command
- [ ] Built-in `eval analyze` subcommand
- [ ] Tests: record invocations, run analyzer, verify report accuracy

**Depends on:** #5

---

### Issue #33: OpenTelemetry observability [DONE]

**Labels:** `phase-3`, `observability`

Add optional OpenTelemetry instrumentation.

**Acceptance criteria:**
- [x] `tooli/telemetry.py`: optional OTel span creation around command execution
- [x] Span attributes: command name, arguments (redacted sensitive), duration, exit code, error category
- [x] Only active when `opentelemetry-api` is installed (optional dependency) and `TOOLI_OTEL_ENABLED=true`
- [x] Zero overhead when disabled (no import of OTel packages)
- [x] Tests: verify spans are created when enabled, verify no import when disabled

**Depends on:** #5

---

### Issue #34: Security policy modes and output sanitization

**Labels:** `phase-3`, `security`

Implement the security middleware for prompt injection resistance and policy enforcement.

**Acceptance criteria:**
- [ ] `tooli/security/sanitizer.py`: output sanitizer that strips ANSI escape codes, control characters, and known injection patterns from structured output fields
- [ ] `tooli/security/policy.py`: `SecurityPolicy` with modes `off`, `standard` (default), `strict`
  - `standard`: sanitize output, require `--force`/`--yes` for destructive commands
  - `strict`: all of standard + `human_in_the_loop` overrides `--yes` for destructive commands
- [ ] Configurable via `Tooli(security_policy="standard")` or `TOOLI_SECURITY_POLICY` env var
- [ ] Audit events: emit structured log entries to stderr for destructive actions, confirmation overrides, and policy denials
- [ ] Tests: verify sanitization strips control characters, verify destructive command requires confirmation, verify strict mode blocks `--yes` override

**Depends on:** #7, #15

---

### Issue #35: Authorization framework [DONE]

**Labels:** `phase-3`, `security`

Add scope-based authorization to commands.

**Acceptance criteria:**
- [x] `@app.command(auth=["scopes:read", "scopes:write"])` decorator argument
- [x] `tooli/auth.py`: `AuthContext` that carries current scopes, populated from env var (`TOOLI_AUTH_SCOPES`), config, or programmatic injection
- [x] Before command execution, check required scopes against `AuthContext`; raise `AuthError` if insufficient
- [x] Schema export includes `auth` requirements per command
- [x] Tests: verify authorized call succeeds, unauthorized call raises `AuthError` with correct exit code

**Depends on:** #7, #12

---

### Issue #36: Cross-platform prompt safety (`/dev/tty` and `CON`)

**Labels:** `phase-3`, `core`, `input`

Upgrade interactive prompt handling beyond the basic `--yes` flag (Phase 1, Issue #6) to support cross-platform TTY separation — reading prompts from `/dev/tty` or `CON` when stdin is a data pipe.

**Acceptance criteria:**
- [ ] When stdin is a data pipe and a command needs user confirmation, read from `/dev/tty` (Unix) or `CON` (Windows) instead of stdin
- [ ] Graceful fallback: if `/dev/tty` / `CON` is unavailable, raise `InputError` with clear message
- [ ] Tests: verify prompt reads from TTY device when stdin is piped (Unix), verify Windows `CON` path, verify fallback error

**Depends on:** #6, #7

---

### Issue #37: Secrets handling (`--secret-file` pattern)

**Labels:** `phase-3`, `security`

Provide a safe pattern for passing secrets to commands.

**Acceptance criteria:**
- [ ] `tooli/input.py`: `SecretInput` type for parameters that accept secrets
- [ ] Resolution: `--secret-file path` reads from file, `--secret-stdin` reads from stdin, `TOOLI_SECRET_*` env vars (with deprecation warning about env var security)
- [ ] Secret values are never logged, never included in structured output, never written to eval recordings
- [ ] Redaction in verbose/debug output: replace with `***REDACTED***`
- [ ] Tests: verify secret is accessible in command, verify it's redacted in all output channels

**Depends on:** #9, #34

---

### Issue #38: Telemetry pipeline (opt-in)

**Labels:** `phase-3`, `observability`

Optional, opt-in usage telemetry for tool developers.

**Acceptance criteria:**
- [ ] `tooli/telemetry_pipeline.py`: anonymous usage metrics (command names, error rates, durations — no arguments, no output data)
- [ ] Disabled by default; enabled only via explicit `TOOLI_TELEMETRY=true` or `Tooli(telemetry=True)`
- [ ] Clear documentation of what is collected and retention policy
- [ ] Local-only by default (writes to `~/.config/tooli/telemetry/`); remote endpoint is opt-in and configurable
- [ ] Tests: verify disabled by default, verify no data collected when off, verify data shape when on

**Depends on:** #15

---

## Phase Gates

Each phase has a definition-of-done gate before the next phase begins:

### Phase 1 Gate
- [ ] All Phase 1 issues are merged
- [ ] Contract tests pass: schema snapshot, JSON envelope snapshot, help output snapshot
- [ ] stdin/file parity tests pass on Linux and macOS
- [ ] Cold startup p95 <= 120ms (measured in CI)
- [ ] A sample multi-command app demonstrates all Phase 1 features

### Phase 2 Gate
- [ ] All Phase 2 issues are merged
- [ ] MCP server passes compliance tests with at least one MCP client (Claude Desktop or similar)
- [ ] Generated SKILL.md, llms.txt, and man page are verified against a reference app
- [ ] OpenAPI schema validates with an OpenAPI linter

### Phase 3 Gate
- [ ] All Phase 3 issues are merged
- [ ] Security policy tests pass (standard + strict modes)
- [ ] Evaluation harness produces accurate reports on a recorded session
- [ ] Cross-platform tests pass on Linux, macOS, and Windows CI runners
