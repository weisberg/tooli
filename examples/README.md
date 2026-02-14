# Tooli Lab: Agent-Native CLI Demo Suite

This repository contains a suite of CLI tools designed to showcase the "Agent-First CLI Contract" enabled by [Tooli](https://github.com/weisberg/tooli).

## The Agent-First CLI Contract

Every tool in this lab adheres to these principles:
1. **Discoverable**: Use `--schema` to see exactly what the tool can do.
2. **Predictable**: Use `--json` or `--jsonl` for stable, machine-readable output.
3. **Safe**: Destructive operations require `--yes` and support `--dry-run`.
4. **Actionable**: Errors include `suggestions` that help agents self-correct.
5. **Universal**: `StdinOr[T]` makes files, URLs, and pipes interchangeable.

---

## The "Best Demo Flow"

Try this sequence with any command (e.g., `repolens summary`):

### 1. Introspect capabilities
```bash
python -m examples.main repolens summary --schema
```

### 2. Run in machine mode
```bash
python -m examples.main repolens summary . --json
```

### 3. Trigger a structured error
```bash
# Run summary on a non-git directory to see the recovery suggestion
python -m examples.main repolens summary /tmp --json
```

### 4. Side-effect command with dry-run
```bash
python -m examples.main patchpilot apply fix.diff --dry-run --json
```

### 5. Flip into MCP mode
```bash
python -m examples.main mcp serve --transport stdio
```

---

## Included Apps

| App | Demonstates |
|---|---|
| **RepoLens** | Structured inventory, JSONL streaming, schema introspection. |
| **PatchPilot** | Dry-run planning, agent-safe behavior, structured errors. |
| **LogSlicer** | `StdinOr` parity, JSONL event streaming, recovery suggestions. |
| **DataWrangler** | Input unification, deterministic JSON, response format variants. |
| **SecretScout** | Structured findings, smart ignore suggestions, opt-in telemetry. |
| **EnvDoctor** | Machine-readable diagnostics, JSONL check stream. |
| **MediaMeta** | `StdinOr` for binary data, dry-run for transcode pipelines. |
| **ConfigMigrate** | Schema-driven discovery, actionable migration hints. |
| **ArtifactCatalog** | JSONL indexing, structured search, one-click MCP serve. |
