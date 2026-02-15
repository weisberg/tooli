# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/weisberg/tooli/releases/tag/v1.0.0
