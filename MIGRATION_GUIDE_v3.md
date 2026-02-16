# Migration Guide: v2 → v3

`tooli` v3 keeps the public decorator API stable. If you have a v2 app, most
files continue to run unchanged.

## Breaking Changes

- None. `@app.command()`, `@app.resource()`, and `@app.prompt()` keep the same
  call signatures.
- `tooli` documentation and manifest output is richer by default, so existing
  automation that parses old SKILL.md text should treat it as a best-effort source.

## Recommended v3 Upgrade Steps

1. **Add return type annotations to command functions** so output schemas are
   discoverable by agents.

   Before:
   ```python
   @app.command()
   def find_files(pattern: str):
       return [("example.py", 123)]
   ```

   After:
   ```python
   from pydantic import BaseModel

   class FileResult(BaseModel):
       path: str
       size: int

   @app.command()
   def find_files(pattern: str) -> list[FileResult]:
       ...
   ```

2. **Add `triggers` / `anti_triggers` / `rules` / `env_vars`** to improve generated
   SKILL.md and manifest quality:

   ```python
   app = Tooli(
       name="file-tools",
       description="File manipulation utilities",
       triggers=["file search", "batch rename", "line counting"],
       anti_triggers=["database operations", "network calls"],
       rules=["Always use --json for agent calls."],
       env_vars={
           "FILE_TOOLS_LOG_LEVEL": {
               "required_for": None,
               "description": "Optional logging level override.",
           },
       },
   )
   ```

3. **Run docs generation** as part of CI or packaging:
   - `python -m pip install tooli` (or your editable workflow)
   - `tooli generate-skill --format skill --output SKILL.md`
   - `tooli generate-skill --format manifest --output agent-manifest.json`
   - `tooli generate-skill --format claude-md --output CLAUDE.md`

4. **Validate generated docs before release**:
   - `tooli generate-skill --validate`
   - Optionally run `tooli eval agent-test` to catch schema/contract regressions.

5. **Opt into tool metadata**
   - Define `workflows` in `Tooli()` for deterministic workflow sections in docs.
   - Or run `generate-skill --infer-workflows` to auto-generate likely command flows.

## v2 Compatibility Notes

- Existing `--help`, `--json`, `--schema`, MCP serving, and observability
  integrations continue to behave as before.
- The generated SKILL.md moved from a minimal format to an agent-ready one
  (sections for parameters, output schema, errors, workflows, and critical rules).
- `--help-agent` output is now YAML-like structured metadata and suitable for
  machine parsing.

If you maintain a custom script that parses command help text directly, review and
update it for SKILL.md sections and the `--agent-manifest` payload.
