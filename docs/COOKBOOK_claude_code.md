# Cookbook: Using Tooli with Claude Code

## Goal

Run Tooli commands from Claude Code with structured, retryable output.

## Pattern

1. Generate command docs:
```bash
tooli-docs skill app_module:app --output SKILL.md
```
2. Invoke commands with JSON envelopes:
```bash
TOOLI_CALLER=claude-code mytool <command> --json
```
3. Use `error.code`, `error.field`, and `suggestion` for retry logic.

## Recommended agent loop

- read schema (`--schema`) before first call
- call with `--json`
- if `ok=false`, patch only the flagged field and retry
