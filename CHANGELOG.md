# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-02-17

### Added
- **Python API**: `app.call(command_name, **kwargs)` for direct in-process command invocation returning typed `TooliResult` objects. Bypasses CLI parsing while preserving validation, error handling, telemetry, and recording.
- **Async Python API**: `app.acall()` awaits async commands directly, threads sync commands via `asyncio.to_thread()`.
- **Streaming API**: `app.stream()` yields individual `TooliResult` items from list-returning commands. `app.astream()` for async iteration.
- **`TooliResult[T]` / `TooliError`**: Frozen generic dataclasses mirroring the CLI JSON envelope as typed Python objects. `unwrap()` raises the appropriate `ToolError` subclass on failure.
- **`get_command(name)`**: Look up command callbacks by name (hyphen/underscore normalized).
- **`CallerCategory.PYTHON_API`**: Enum value identifying in-process Python API calls in telemetry.
- **Capabilities metadata**: `capabilities=[...]` parameter on `@app.command()` for declaring granular permissions (e.g., `["fs:read", "fs:write"]`). Rendered in SKILL.md, AGENTS.md, CLAUDE.md, manifest, and schema.
- **Security enforcement**: `TOOLI_ALLOWED_CAPABILITIES` environment variable in STRICT security policy mode blocks commands with undeclared capabilities. Supports wildcard matching (`fs:*`).
- **Handoffs metadata**: `handoffs=[{"command": "...", "when": "..."}]` for multi-agent workflow orchestration. Rendered in SKILL.md composition patterns and AGENTS.md.
- **Delegation hints**: `delegation_hint="..."` for agent-facing guidance on when to delegate to a command.
- **Error field mapping**: `field` parameter on all `ToolError` subclasses links errors to specific input parameters. Preserved through `TooliError` → `to_exception()` roundtrip.
- **Output schema in envelope**: `output_schema` field in `EnvelopeMeta` when `--response-format detailed` or `TOOLI_INCLUDE_SCHEMA=true`.
- **AGENTS.md generator**: `generate-agents-md` builtin produces GitHub Copilot / OpenAI Codex compatible documentation.
- **Agent SDK integration examples**: `examples/integrations/` with 4 framework examples (Claude SDK, OpenAI Agents, LangChain, Google ADK) using both Python API and subprocess approaches.
- **v5 metadata on all 18 example apps**: `capabilities` on all 65 commands, `handoffs` and `delegation_hint` on 6 priority apps.
- **Python API section in AGENT_INTEGRATION.md**: Documentation for `app.call()`, `app.stream()`, and framework integration patterns.
- **120+ new tests** across 8 test files. Total: 529+ tests.

### Changed
- `EnvelopeMeta` now includes optional `output_schema` field.
- `CommandMeta` now includes `capabilities`, `handoffs`, `delegation_hint` fields.
- `ToolSchema` includes `capabilities`, `handoffs`, `delegation_hint`.
- Manifest renders capabilities, handoffs, and delegation hints per command.
- `ToolError.to_dict()` conditionally includes `field` when not None.

## [4.1.0] - 2026-02-17

### Added
- **Caller-Aware Agent Runtime**: `TOOLI_CALLER` environment variable convention for explicit agent identification with 100% confidence, zero overhead.
- **5-category heuristic detection** (`tooli/detect.py`): Identifies callers as `human`, `ai_agent`, `ci_cd`, `container`, or `unknown_automation` via environment variables, process tree inspection, TTY status, and container markers.
- **`detect-context` builtin command**: Hidden command available on every Tooli app to inspect the current execution context (useful for debugging agent integrations).
- **Caller metadata in envelope**: `caller_id`, `caller_version`, and `session_id` fields in `EnvelopeMeta`, populated automatically when `TOOLI_CALLER` is set.
- **OTel caller span attributes**: `tooli.caller_id`, `tooli.caller_version`, `tooli.session_id` attributes on telemetry spans.
- **InvocationRecord schema v2**: Added `caller_id` and `session_id` fields to invocation recordings.
- **Manifest `caller_convention`**: Agent manifest now includes `caller_convention` section documenting the `TOOLI_CALLER` protocol.
- **Adaptive confirmation**: Agents with `--yes` automatically skip destructive command confirmation; without `--yes`, agents receive structured error with recovery suggestion.
- **Adaptive help formatting**: Convention-identified agents (`TOOLI_CALLER` set) receive structured YAML help from `--help` instead of Rich-formatted text.
- **Agent Integration section in SKILL.md**: Auto-generated documentation for the `TOOLI_CALLER` convention in every generated SKILL.md.
- **TOOLI_CALLER hints in CLAUDE.md**: Generated CLAUDE.md files now include guidance on setting `TOOLI_CALLER`.
- **Well-known caller identifiers**: 21 pre-registered agent identifiers (Claude Code, Cursor, Aider, Devin, LangChain, CrewAI, etc.).
- **`docs/AGENT_INTEGRATION.md`**: Comprehensive guide for agent developers on using the `TOOLI_CALLER` convention.
- **100 new tests** across `tests/test_detect.py` (82 tests) and `tests/test_caller_integration.py` (18 tests). Total: 359 tests.
- Exported `CallerCategory`, `ExecutionContext`, `detect_execution_context` from `tooli` package.

### Changed
- `_is_agent_mode()` now uses detection module fallback instead of simple TTY check.
- `InvocationRecord` `SCHEMA_VERSION` bumped from 1 to 2 (additive, not breaking).
- `_needs_human_confirmation()` accepts `is_agent_caller` parameter for adaptive behavior.

## [4.0.0] - 2026-02-17

### Added
- **Agent Skill Platform**: Task-oriented SKILL.md generation with commands grouped by `task_group`, "When to use" guidance, and "If Something Goes Wrong" recovery sections.
- **`--agent-bootstrap` global flag**: Any command can produce a deployable SKILL.md with auto-detection of target environment (Claude Code, Claude, or generic agent).
- **`PipeContract` type** (`tooli/pipes.py`): Declare input/output formats for command composition. Auto-inferred composition patterns in SKILL.md (pipe chains, ReadOnly→Destructive preview pairs, dry-run patterns, pagination chains).
- **`generate-skill --target`**: Target-specific SKILL.md output — `generic-skill`, `claude-skill`, or `claude-code`.
- **`tooli init` scaffolding** (`tooli/init.py`): Create new projects with pyproject.toml, app.py, tests, SKILL.md, CLAUDE.md, README.md. Includes `--from-typer` for Typer migration.
- **Source-level agent hints** (`tooli/docs/source_hints.py`): Generate and insert `# tooli:agent ... # tooli:end` metadata blocks in source files.
- **Enhanced CLAUDE.md generator** (`tooli/docs/claude_md_v2.py`): Build & Test, Architecture, Agent Invocation, Key Patterns, Development Workflow sections.
- **Metadata coverage reporter** (`tooli/eval/coverage.py`): Reports missing examples, output schemas, error codes, token estimates, and warnings.
- **Upgrade analyzer** (`tooli/upgrade.py`): Analyzes apps and suggests metadata improvements with optional code stub generation.
- **LLM-powered skill evaluation** (`tooli/eval/skill_roundtrip.py`): Generates SKILL.md, feeds to LLM, verifies invocations. Opt-in, requires API key.
- **MCP skill resources**: Auto-registered `skill://manifest` and `skill://documentation` resources on MCP server startup.
- **New `CommandMeta` fields**: `pipe_input`, `pipe_output`, `when_to_use`, `expected_outputs`, `recovery_playbooks`, `task_group`.
- **73 new tests** across 7 test files (259 total).
- **6 example apps updated** with v4 metadata: docq, gitsum, envdoctor, taskr, logslicer, repolens.
- `MIGRATION_GUIDE_v4.md` with v3→v4 migration steps.

### Changed
- `generate-skill` builtin now uses the v4 generator by default.
- Manifest output includes `pipe_input`, `pipe_output`, `task_group`, `when_to_use` fields.
- `PipeContract` exported from `tooli.__init__`.

## [3.0.0] - 2026-02-16

### Added
- Added v3 documentation workflow primitives:
  - `generate-skill --validate`, `--infer-workflows`, `--output`, and manifest/Claude output modes.
  - SKILL.md token-budget estimation helper (`estimate_skill_tokens`) and corresponding regression tests.
- Added `MIGRATION_GUIDE_v3.md` with explicit v2→v3 migration steps.
- Added native backend marker support for `tooli.backends.native.Argument` and `Option` to accept
  keyword metadata (`help=`, `is_flag=`, etc.) and native `--help-agent` YAML-like output.

## [2.0.0] - 2026-02-16

### Added
- Added a hidden `orchestrate run` command for programmatic multi-tool workflows, with JSON and Python payload plans, per-step summarization, and optional continue-on-error execution.
- Added `agent` and machine-facing contracts to docs and onboarding files (`llms.txt`, `CLAUDE.md`, `PLAN.md`, `PRD.md`) for 2.0 release communication.

### Changed
- Updated roadmap documentation to reflect implemented v2 staging progress (Programmatic orchestration runtime is now complete; remaining v2 issues remain open).
- Bumped package release metadata for v2.0.0.

## [1.2.0] - 2026-02-16

### Added
- Added top-level `tooli` launcher for MCP serving by module path (`--transport`, `--defer-loading`).
- Added deferred MCP discovery with `search_tools` and `run_tool`.
- Added output token-budget support via `max_tokens` metadata and `tooli_read_page` artifact reader.
- Added scoped script execution support for multi-tool workflows (`orchestrate run`) in the same release line.
- Added opt-in Python payload mode (`allow_python_eval` and `--python-eval`) for command argument injection.
- Added command-level approval signals (`requires_approval` and `danger_level`) for higher-confidence HITL behavior.

### Changed
- Extended MCP export with `defer_loading` mode.
- Exposed new governance metadata in command behavior output and docs.

## [1.1.0] - 2026-02-16

### Added
- Added v1.1 stabilization workflow checks and release documentation for ongoing hardening.
- Added roadmap and issue-planning expansion for v2.0 Agent-Environment Interface capabilities.
- Added `scripts/check_v11_hardening.py` and CI enforcement for pre-release version consistency.

### Changed
- Set PyPI long description to `pypi/pypi_project.md` with a Tooli-focused project page.

## [1.0.2] - 2026-02-15

### Changed
- Set PyPI long description to `pypi/pypi_project.md` with a Tooli-focused project page.

## [1.0.1] - 2026-02-15

### Changed
- Updated all project documentation (README, examples, PLAN, PRD, CLAUDE.md)
- Added CI/PyPI/license badges to README
- Added optional extras install instructions (`tooli[mcp]`, `tooli[api]`)
- Rewrote examples README with all 18 apps organized by category
- Added CONTRIBUTING.md, CODE_OF_CONDUCT.md, CHANGELOG.md
- Added GitHub Actions publish workflow with OIDC trusted publishing
- Added issue templates for bug reports and feature requests
- Added `tomli` dependency for Python 3.10 compatibility

## [1.0.0] - 2026-02-15

### Added
- Core framework: `Tooli` class extending Typer with agent-native defaults
- Output modes: AUTO, JSON, JSONL, TEXT, PLAIN with `--output` flag
- Structured error hierarchy: InputError, AuthError, StateError, ToolRuntimeError, InternalError
- Annotations: ReadOnly, Destructive, Idempotent, OpenWorld (composable with `|`)
- Cursor-based pagination with `--limit`, `--cursor`, `--fields`, `--filter`
- `StdinOr[T]` for unified input from files, URLs, and stdin
- `SecretInput[T]` with automatic redaction in output and error messages
- `@dry_run_support` decorator with `record_dry_action()` for previewing side effects
- Process-local idempotency tracking with key support
- MCP server support (stdio, HTTP, SSE) via `tooli[mcp]`
- HTTP API server with OpenAPI 3.1 schema generation via `tooli[api]` (experimental)
- Auth context framework with scope-based access control
- Security policy (OFF, STANDARD, STRICT) with output sanitization
- Opt-in telemetry pipeline with local-first storage and configurable retention
- Invocation recording and analysis for eval workflows
- Transform pipeline: NamespaceTransform, VisibilityTransform
- Versioned commands with automatic `-v{X}` suffix handling
- Documentation generation: SKILL.md, llms.txt, Unix man pages
- 9 example apps: note_indexer, docq, gitsum, csvkit_t, syswatch, taskr, proj, envar, imgsort

[5.0.0]: https://github.com/weisberg/tooli/releases/tag/v5.0.0
[4.1.0]: https://github.com/weisberg/tooli/releases/tag/v4.1.0
[4.0.0]: https://github.com/weisberg/tooli/releases/tag/v4.0.0
[3.0.0]: https://github.com/weisberg/tooli/releases/tag/v3.0.0
[2.0.0]: https://github.com/weisberg/tooli/releases/tag/v2.0.0
[1.2.0]: https://github.com/weisberg/tooli/releases/tag/v1.2.0
[1.1.0]: https://github.com/weisberg/tooli/releases/tag/v1.1.0
[1.0.2]: https://github.com/weisberg/tooli/releases/tag/v1.0.2
[1.0.1]: https://github.com/weisberg/tooli/releases/tag/v1.0.1
[1.0.0]: https://github.com/weisberg/tooli/releases/tag/v1.0.0
