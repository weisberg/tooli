# Migration Guide: v5 to v6

This guide maps removed or extracted v5 features to v6 replacements.

## Core removals and replacements

| Removed / changed | v6 replacement |
|---|---|
| `generate-skill`, `generate-claude-md`, `generate-agents-md` built-ins | `tooli-docs` package (`tooli-docs skill|claude-md|agents-md ...`) |
| `export --target ...` built-in | `tooli-export` package (`tooli-export openai|langchain|adk|python ...`) |
| `tooli eval ...` built-ins | external CI checks and purpose-built eval scripts |
| `tooli/docs/source_hints.py` comment hints (`# tooli:agent`) | rely on `--schema` and manifest output |
| `PipeContract` / `tooli/pipes.py` | JSON/JSONL command contracts and schema-driven orchestration |
| multi-backend selection (`backend=...`) | native-only runtime path |

## What to update in your automation

1. Replace any `generate-*` built-in invocation with `tooli-docs`.
2. Replace any `export` built-in invocation with `tooli-export`.
3. Remove `eval` built-in usage from pipelines.
4. Ensure agents consume `--json`, `--schema`, and metadata-driven docs.

## Example command rewrites

```bash
# Before (v5)
mytool generate-skill --output-path SKILL.md
mytool export --target langchain --mode import

# After (v6)
tooli-docs skill mytool_app:app --output SKILL.md
tooli-export langchain mytool_app:app --mode import
```
