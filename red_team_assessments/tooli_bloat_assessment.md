# Tooli Has Lost the Plot: A Case for Radical Simplification

## The Original Promise

Tooli started with a clean, beautiful idea: **write a Python function, get a CLI that agents can use.** That's it. That was the whole pitch. A developer decorates a function with `@app.command()`, adds type hints and a docstring, and tooli handles the rest — argument parsing, JSON output for agents, Rich output for humans, structured errors when things go wrong.

This was a genuinely novel insight. Every other CLI framework (Typer, Click, Fire, argparse) was designed exclusively for human users. Tooli recognized that the primary consumer of CLI tools in 2025-2026 is increasingly an AI agent, and that agents need structured output, parseable errors, and discoverable schemas — not pretty terminal formatting. The "Typer replacement for the agent era" positioning was sharp, defensible, and true.

Somewhere between v2 and the v4.0 PRD, that clarity evaporated. Tooli is no longer a CLI framework. It's trying to be a skill platform, an MCP server framework, a documentation generator, a project scaffolder, a migration tool, a certification authority, a multi-format export pipeline, and an eval harness. It has become the thing it was supposed to replace: a bloated framework that tries to do everything and does none of it as well as it should.

---

## The Bloat Inventory

Let's be honest about what tooli is carrying. Here is every subsystem, feature surface, and output mode that currently exists or is planned in the v4.0 PRD:

**Core CLI framework** (this is what tooli should be)
- `@app.command()` decorator with type-hint-to-schema pipeline
- Dual-mode output (Rich for humans, JSON for agents)
- Structured error envelope with `{ok, result, error, meta}`
- `--json`, `--jsonl`, `--plain`, `--quiet` output flags

**Documentation generation** (a second product hiding inside the first)
- `generate-skill` subcommand with `--detail-level`, `--validate`, `--format`
- SKILL.md generation with YAML frontmatter, quick reference tables, parameter tables, error catalogs
- Token-budget tiering (summary, standard, full)
- `--agent-bootstrap` global flag (distinct from `generate-skill`)
- `--agent-manifest` global flag (JSON manifest, distinct from SKILL.md)
- `generate-claude-md` command for Claude Code-specific docs
- AGENTS.md generation for GitHub Copilot compatibility
- `tooli:agent` / `tooli:end` source-level hint blocks
- Jinja2 template support for custom SKILL.md sections (proposed)
- `upgrade-metadata --apply` and `--enrich-docstrings` commands

**MCP server** (a third product)
- One-command MCP server mode (`serve_mcp`)
- MCP tool registration with schema mapping
- MCP skill resources with `skill://` URI scheme
- Tool annotations (`ReadOnly`, `Destructive`, `Idempotent`)
- Deferred loading for Tool Search Tool compatibility

**Multi-framework export** (a fourth product)
- `--export openai` / `--export langchain` / `--export adk` / `--export ptc`
- `allowed_callers` for PTC compatibility
- `input_examples` mapping for Anthropic's tool use format
- Schema export in multiple formats (MCP, OpenAI, JSON Schema)

**Project scaffolding and migration** (a fifth product)
- `tooli init` with skill-ready defaults
- `tooli init --from-typer` migration from existing Typer apps
- Click migration support (proposed)

**Eval and validation** (a sixth product)
- `eval agent-test` harness
- `tooli validate --ptc` certification command
- Verified examples with expected output snapshots
- LLM round-trip eval (proposed)
- Coverage reports (proposed)

**Advanced composition** (a seventh product)
- Pipe composition contracts with `accepts`/`produces` declarations
- Streaming vs. batch distinction for pipe semantics
- Workflow inference (`--infer-workflows`)
- `task_group` ordering with semantic understanding
- `StdinOr[T]` input unification for file/stdin/URL parity

**Miscellaneous feature surface**
- `--dry-run` global flag
- `--schema` global flag
- Agent context detection via environment variables (Claude Code, generic)
- Error recovery playbooks (multi-step)
- `is_retryable` / `suggestion.action` error contract
- Behavioral annotations beyond MCP (`ReadOnly`, `Idempotent` on schema level)
- Token counting of generated documentation
- Native backend (argparse-based, replacing Typer dependency)
- Pydantic model integration for output schemas

Count the distinct subsystems: **seven**, not including the miscellaneous surface area. This is not a CLI framework. This is an entire developer platform masquerading as a library. And critically, **none of it has achieved the depth and quality it would need to actually win** in any of these individual categories.

---

## Why This Happened

The bloat follows a recognizable pattern. Each feature started as a reasonable answer to a real question:

1. "Agents need to discover tools" → SKILL.md generation
2. "Different agents use different formats" → multi-format export
3. "MCP is the standard" → MCP server mode
4. "Developers need onboarding" → project scaffolding
5. "We need to prove it works" → eval harness
6. "Claude Code works differently than generic agents" → Claude-specific output
7. "Tools need to compose" → pipe contracts

Every one of these is a legitimate need. The mistake was deciding that tooli should solve all of them. The result is a framework where the core decorator-to-CLI pipeline — the thing that actually matters — is surrounded by so much ancillary machinery that a developer evaluating tooli can't tell what it actually *is*.

Compare this with the tools tooli is competing against. Typer does one thing: it turns type-annotated Python functions into CLI apps. That's it. That's the whole library. It doesn't generate documentation in five formats. It doesn't scaffold projects. It doesn't run as an MCP server. And it has 15,000+ GitHub stars because the one thing it does, it does extremely well.

---

## The Prescription: What to Cut

The guiding principle is simple: **tooli is a CLI framework that makes agent-friendly tools. Everything else is either a plugin, a separate tool, or someone else's problem.**

### Keep (the irreducible core)

These features are what make tooli *tooli*. They should be polished to perfection:

1. **`@app.command()` decorator with type-hint-to-schema pipeline.** This is the product. A developer writes a typed Python function, and tooli gives them a CLI that agents can call with `--json` and get a structured `{ok, result, error, meta}` envelope back. The schema is automatically generated from type hints and Pydantic models. This must be rock-solid, beautifully documented, and faster than Typer.

2. **Dual-mode output.** Auto-detect TTY for human-readable Rich output vs. JSON for agents. Keep `--json` and `--jsonl`. These are core to the identity.

3. **Structured errors.** Error codes, categories, `is_retryable`, and a one-line `suggestion`. Not multi-step "recovery playbooks" — a single `suggestion` field that tells an agent what to try next. This is a differentiator and it's the right level of abstraction.

4. **JSON Schema export.** `mytool --schema` outputs the JSON Schema for all commands. One format. Not five. JSON Schema is the universal interchange format. OpenAI function calling consumes JSON Schema. MCP consumes JSON Schema. Anthropic's tool use consumes JSON Schema. Everyone consumes JSON Schema. Tooli should export JSON Schema and let consumers adapt it to their format.

5. **The native backend.** Zero dependencies beyond Pydantic is a legitimate advantage. Keep it. But stop treating "native vs. Typer backend" as a feature — just ship the native backend as the default and drop the Typer backend entirely. One backend. No choice. Less code.

### Cut entirely

6. **MCP server mode.** This is a different product. FastMCP already exists and does this well. An MCP server has different lifecycle management, different transport concerns (stdio, SSE, HTTP), different authentication patterns, and different scaling characteristics than a CLI framework. Tooli should export JSON Schema that *FastMCP can consume*, not try to be an MCP server itself. If someone wants their tooli commands as MCP tools, they should write five lines of FastMCP glue code. That's fine. That's not tooli's job.

7. **SKILL.md generation.** This is the most controversial cut, but hear me out. SKILL.md is a *Claude-specific documentation format*. It's not a standard. It's not consumed by OpenAI, Google, or any other agent platform. Generating high-quality SKILL.md requires solving a documentation-generation problem that is fundamentally different from the CLI-framework problem. The v4.0 PRD acknowledges this: the current generator produces "flat and mechanical" output while hand-written skills are "rich and task-oriented." Making the generator produce genuinely good output requires task-oriented rewriting, verified examples with output snapshots, semantic grouping, and all the complexity in the PRD. This is a documentation-quality problem, not a CLI-framework problem. It should be a separate tool — call it `skillgen` or `agent-docs` — that can read any CLI's JSON Schema and `--help` output and generate SKILL.md from it. This separate tool can then improve independently, support non-tooli CLIs, and not burden the core framework with its complexity.

8. **`--agent-bootstrap` and `--agent-manifest` global flags.** These inject behavior into every tooli app that most users never asked for. The agent manifest is just the JSON Schema output repackaged. The bootstrap is just the SKILL.md generator triggered by a flag. Both should go away with the SKILL.md generator.

9. **Multi-format export (`--export openai/langchain/adk/ptc`).** Tooli exports JSON Schema. That's the contract. If someone needs an OpenAI function-calling wrapper, that's a five-line transformation they write once. Maintaining format-specific exporters means tooli has to track every API change from every LLM provider. That's an unbounded maintenance burden for a CLI framework.

10. **Project scaffolding (`tooli init`).** A `cookiecutter` template or a single page in the docs that says "here's how to start a project" is sufficient. `tooli init` is a feature that gets used once per project and then never again. It's not worth the code it takes to maintain, and it's definitely not worth the cognitive overhead of "wait, is tooli a CLI framework or a project generator?"

11. **Typer migration (`tooli init --from-typer`).** This is a clever idea and absolutely not worth building. Migration tools are notoriously fragile, and the Typer-to-tooli migration is simple enough to document in a one-page guide: "replace `import typer` with `import tooli`, change `typer.Typer()` to `tooli.Tooli()`, add return type annotations." A human or an AI agent can do this in five minutes with a find-and-replace guide.

12. **Pipe composition contracts.** This is solving a problem that doesn't exist yet. The `accepts`/`produces` system, streaming vs. batch distinction, and composition inference add significant complexity to the decorator API for a feature that has zero proven demand. Unix pipes already work. JSONL already streams. If composition contracts become necessary, they can be added later as a plugin.

13. **Eval harness and certification.** `tooli validate --ptc`, LLM round-trip eval, coverage reports — these are testing tools, not CLI framework features. They belong in a separate `tooli-eval` package or, better yet, in the CI/CD recipes in the docs. Embedding an eval framework inside a CLI framework is scope creep.

14. **`tooli:agent` source-level hint blocks.** This is a custom comment format that no tool, linter, or IDE understands. It's tooli inventing its own metadata standard when JSON Schema already exists. Agents don't read Python source comments for tool discovery — they read schemas, help output, or documentation. Cut it.

15. **Claude Code-specific integration.** `generate-claude-md`, environment detection for Claude Code vs. generic agents, `/mnt/skills/` path conventions — these couple tooli to a single vendor's implementation details. Tooli should be agent-agnostic. If Claude Code needs specific integration, that's a plugin or a recipe in the docs, not a core feature.

16. **Error recovery playbooks.** Multi-step recovery strategies are over-engineered. A structured error with a code, category, message, and a single `suggestion` string is the right level of abstraction. The agent decides what to do with the suggestion. Tooli doesn't need to model multi-step recovery flows.

17. **`--dry-run` as a framework feature.** Dry-run is application-specific. A file deletion tool's dry-run is completely different from a database migration tool's dry-run. Tooli can't meaningfully implement this at the framework level — it can only add a `--dry-run` flag and pass it through to the command function. That's not a feature; that's a boolean parameter the developer can add themselves.

18. **Token-budget tiering for documentation.** "Summary mode" vs. "standard mode" vs. "full mode" for generated docs is optimizing for a constraint (LLM context windows) that is expanding rapidly and that the documentation consumer (the agent framework) should manage, not the documentation producer.

19. **AGENTS.md generation.** This is GitHub Copilot's convention. Like SKILL.md is Claude's convention. Tooli shouldn't be in the business of generating every agent platform's preferred documentation format. Export JSON Schema. Let each platform's tooling generate its own preferred format from the schema.

### Promote to plugins (optional installs)

20. **`StdinOr[T]` input unification.** This is a genuinely useful utility for tools that process files, but it's a type helper, not a core framework feature. Ship it as `tooli-io` or include it as an optional import from `tooli.contrib`.

21. **Rich output formatting.** The dual-mode auto-detection should stay, but the specific Rich formatting (tables, panels, syntax highlighting) should be a plugin that developers can opt out of entirely. Some tools just need `print()` for humans and `json.dumps()` for agents.

---

## What the Lean Tooli Looks Like

After these cuts, tooli's entire public API fits on a single page:

```python
from tooli import Tooli, Option, Argument

app = Tooli(name="mytool", description="Does a thing")

@app.command()
def find_files(
    pattern: str = Argument(help="Glob pattern to match"),
    root: str = Option(".", help="Root directory"),
    max_depth: int = Option(10, help="Maximum search depth"),
) -> list[FileResult]:
    """Find files matching a pattern."""
    ...
```

The developer gets:
- `mytool find-files "*.py"` → Rich table for humans
- `mytool find-files "*.py" --json` → `{ok: true, result: [...], meta: {...}}`
- `mytool find-files "*.py" --jsonl` → one result per line, streaming
- `mytool --schema` → JSON Schema for all commands
- Structured errors with codes, categories, and suggestions on failure

That's the whole product. Five things. All of them done extremely well. All of them tested, documented, and polished. No scaffolding. No migration. No MCP. No SKILL.md. No eval. No pipe contracts. No multi-format export.

---

## The Strategic Argument

The counterargument to all of this is obvious: "But agents need discovery, and SKILL.md is how Claude discovers tools, and MCP is the standard, and if we don't integrate we won't get adopted."

This argument conflates *tooli the framework* with *the ecosystem around tooli*. Tooli's job is to make it trivially easy to write a CLI tool that agents can use. The ecosystem's job — separate tools, plugins, documentation, recipes — is to connect those tools to specific agent platforms.

Consider how other successful frameworks handle this boundary:

- **FastAPI** doesn't generate Kubernetes manifests, even though most FastAPI apps run on Kubernetes. It generates OpenAPI Schema. Helm charts, Docker configs, and deployment recipes are separate.
- **Typer** doesn't generate man pages, even though many CLI tools need them. It generates `--help` output. Man page generation is a separate tool (`click-man`).
- **Pydantic** doesn't generate database schemas, even though many Pydantic models map to database tables. It generates JSON Schema. SQLAlchemy integration is a separate library (`sqlmodel`).

Tooli should follow the same pattern. It generates JSON Schema and structured output. SKILL.md generation, MCP serving, platform-specific integration, and eval tooling are separate concerns handled by separate tools that consume tooli's schema output.

This also makes tooli more defensible. A lean framework with one clear purpose is harder to replace than a sprawling platform with seven mediocre subsystems. If someone builds a better SKILL.md generator, tooli doesn't care — its schema output feeds the new generator just as well. If MCP gets replaced by a new protocol, tooli doesn't need to change — only the MCP adapter needs updating.

---

## The Dependency Test

A useful heuristic: **if a feature requires tooli to track changes in an external system it doesn't control, it doesn't belong in tooli.**

- SKILL.md format changes? Claude's problem, not tooli's.
- OpenAI function-calling schema evolves? OpenAI's problem.
- MCP protocol adds new capabilities? FastMCP's problem.
- PTC adds new `allowed_callers` values? Anthropic's problem.
- GitHub Copilot changes AGENTS.md conventions? GitHub's problem.

Tooli should depend on exactly one external standard: JSON Schema. Everything else is someone else's concern.

---

## Implementation Path

The path from current state to lean tooli is not a rewrite. It's a series of extractions:

1. **v4.0**: Extract `generate-skill`, `--agent-bootstrap`, `--agent-manifest`, and all SKILL.md-related code into a separate `tooli-skills` package. It imports from `tooli` and reads schemas — it's a consumer, not a component.

2. **v4.1**: Extract MCP server mode into `tooli-mcp`. Same pattern: it reads tooli's schema and wraps commands as MCP tools.

3. **v4.2**: Drop the Typer backend entirely. Native backend only. Remove `tooli[typer]` optional dependency. This simplifies the codebase significantly.

4. **v4.3**: Remove `tooli init`, `--from-typer`, pipe contracts, eval harness, source hints, and multi-format export. Replace with documentation: "How to use tooli with Claude Code," "How to use tooli with MCP," "How to migrate from Typer."

5. **v5.0**: The lean release. Core framework only. Single README. Single tutorial. One clear pitch: "Write a Python function. Get a CLI that agents love."

Each extraction is backwards-compatible because the extracted packages still exist — they're just not bundled. Developers who need SKILL.md generation install `tooli-skills`. Developers who need MCP serving install `tooli-mcp`. The core framework stays small, fast, and focused.

---

## Conclusion

Tooli's original insight — that CLI tools need to be agent-friendly — is more true today than when the project started. But the response to that insight has been to absorb every adjacent problem into the framework itself. The result is a project that's difficult to explain, difficult to evaluate, and difficult to maintain.

The fix is not to add more features. The fix is to ruthlessly subtract until what remains is undeniable: the best way to turn a Python function into a CLI tool that both humans and agents can use. Everything else is a plugin, a recipe, or someone else's responsibility.

Tooli doesn't need to be a platform. It needs to be a library. A very, very good library.
