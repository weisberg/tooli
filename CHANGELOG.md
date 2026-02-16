# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[2.0.0]: https://github.com/weisberg/tooli/releases/tag/v2.0.0
[1.2.0]: https://github.com/weisberg/tooli/releases/tag/v1.2.0
[1.1.0]: https://github.com/weisberg/tooli/releases/tag/v1.1.0
[1.0.2]: https://github.com/weisberg/tooli/releases/tag/v1.0.2
[1.0.1]: https://github.com/weisberg/tooli/releases/tag/v1.0.1
[1.0.0]: https://github.com/weisberg/tooli/releases/tag/v1.0.0
