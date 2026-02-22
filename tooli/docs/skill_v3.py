"""Next-generation SKILL.md generator with richer agent-facing sections."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, get_args, get_origin

from tooli.command_meta import get_command_meta
from tooli.schema import generate_tool_schema

if TYPE_CHECKING:
    from tooli.app import Tooli


DetailLevel = Literal["auto", "full", "summary"]

_DEFAULT_MAX_COMMANDS_FOR_FULL = 20


def estimate_skill_tokens(content: str, model: str = "o200k_base") -> int:
    """Estimate token count for generated documentation.

    Uses ``tiktoken`` when available and falls back to whitespace token
    estimation to avoid hard dependency requirements.
    """
    if not content:
        return 0

    try:
        import tiktoken  # type: ignore[import-not-found]

        # Most tool docs are short and use plain text/code blocks; the base
        # encoding used by modern OpenAI models is a good proxy.
        encoder = tiktoken.get_encoding(model)
        return len(encoder.encode(content))
    except Exception:
        return len(content.split())


def _readable_type(annotation: Any) -> str:
    if annotation is inspect.Signature.empty:
        return "any"
    if annotation is Any:
        return "any"
    if isinstance(annotation, str):
        return annotation
    if get_origin(annotation) is list:
        args = get_args(annotation)
        if args:
            return f"list[{_readable_type(args[0])}]"
        return "list"
    if get_origin(annotation) is tuple:
        args = get_args(annotation)
        if args:
            return f"tuple[{', '.join(_readable_type(arg) for arg in args)}]"
        return "tuple"
    if get_origin(annotation) is dict:
        args = get_args(annotation)
        if len(args) == 2:
            return f"dict[{_readable_type(args[0])}, {_readable_type(args[1])}]"
        return "dict"

    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if origin is not None and args:
            return f"{_simple_type_name(origin)}[{', '.join(_readable_type(arg) for arg in args)}]"
        return _simple_type_name(origin)

    return _simple_type_name(annotation)


def _simple_type_name(annotation: Any) -> str:
    if annotation is None:
        return "none"
    if annotation is inspect.Signature.empty:
        return "any"
    if isinstance(annotation, str):
        return annotation
    if annotation is Any:
        return "any"
    if hasattr(annotation, "__name__"):
        return str(annotation.__name__)
    if getattr(annotation, "_name", None):
        return str(annotation._name)
    return str(annotation)


def _annotation_description(annotation: Any) -> str:
    if get_origin(annotation) is not None:
        args = get_args(annotation)
        if args:
            for meta in args[1:]:
                help_text = getattr(meta, "help", None)
                if help_text:
                    return str(help_text)
    return ""


def _normalize_default(value: Any) -> str:
    if value is inspect.Signature.empty or value is Ellipsis:
        return "--"
    if value is None:
        return "`None`"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value.replace("\n", "\\n")
    if isinstance(value, (list, tuple)):
        return f"`{','.join(map(str, value))}`"
    return str(value)


def _command_signature_params(callback: Any) -> list[tuple[str, Any, Any, str]]:
    try:
        type_hints = inspect.get_annotations(callback)
    except Exception:
        type_hints = {}

    params: list[tuple[str, Any, Any, str]] = []
    for param in inspect.signature(callback).parameters.values():
        if param.kind in {inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL}:
            continue
        if param.name in {"ctx", "context"}:
            continue
        annotation = type_hints.get(param.name, param.annotation)
        description = _annotation_description(annotation)
        if isinstance(annotation, tuple) and getattr(annotation[0], "__metadata__", None):
            annotation = annotation[0]
        params.append((param.name, annotation, param.default, description))
    return params


def _is_required_param(default: Any) -> bool:
    return default is inspect.Signature.empty or default is Ellipsis


def _collect_visible_commands(app: Tooli) -> list[Any]:
    return [tool_def for tool_def in app.get_tools() if not tool_def.hidden]


def _extract_tokens(text: str, limit: int = 3) -> list[str]:
    if not text:
        return []
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", text.lower())
    return [word for word in words[:limit]]


def _annotation_labels(callback: Any | None) -> list[str]:
    meta = get_command_meta(callback).annotations
    if meta is None:
        return []
    labels: list[str] = []
    if getattr(meta, "read_only", False):
        labels.append("read-only")
    if getattr(meta, "idempotent", False):
        labels.append("idempotent")
    if getattr(meta, "destructive", False):
        labels.append("destructive")
    if getattr(meta, "open_world", False):
        labels.append("open-world")
    return labels


def _split_error_message(raw_message: str) -> tuple[str, str]:
    for sep in [" -> ", ";", "|", ":"]:
        if sep in raw_message:
            condition, recovery = raw_message.split(sep, 1)
            return condition.strip(" -"), recovery.strip()
    return raw_message.strip(), "See command docs for recovery action."


def _error_category(code: str) -> str:
    if not code.startswith("E") or len(code) < 2:
        return "other"
    return {
        "1": "input",
        "2": "auth",
        "3": "state",
        "4": "runtime",
        "5": "internal",
        "7": "runtime",
    }.get(code[1], "other")


def _is_stdin_or_annotation(annotation: Any) -> bool:
    if annotation is inspect.Signature.empty:
        return False
    origin = get_origin(annotation)
    if origin is not None and _simple_type_name(origin) == "StdinOr":
        return True
    return "StdinOr[" in str(annotation)


def _command_reference_rows_for_tool(app_name: str, tool_def: Any) -> list[tuple[str, str]]:
    callback = tool_def.callback
    meta = get_command_meta(callback)
    if meta.examples:
        raw_args = meta.examples[0].get("args", [])
        if isinstance(raw_args, list):
            command = " ".join([app_name, tool_def.name] + [str(arg) for arg in raw_args if arg is not None])
            label = meta.examples[0].get("description") or tool_def.name
            return [(label, command)]

    required_args = [
        f"<{name}>"
        for name, _annotation, default, _description in _command_signature_params(callback)
        if _is_required_param(default)
    ]
    description = tool_def.help or callback.__doc__ or tool_def.name
    label = " ".join(line.strip() for line in description.splitlines() if line.strip()) or str(tool_def.name)
    command = f"{app_name} {tool_def.name}" + (" " + " ".join(required_args) if required_args else "")
    return [(label, command)]


def _command_examples(app_name: str, tool_def: Any) -> list[str]:
    callback = tool_def.callback
    examples = get_command_meta(callback).examples
    lines = ["#### Examples", ""]
    if examples:
        for example in examples:
            args = example.get("args")
            if isinstance(args, list):
                arg_text = " ".join(str(arg) for arg in args if arg is not None)
            else:
                arg_text = ""
            command = f"{app_name} {tool_def.name} {arg_text}".strip()
            lines.append("```bash")
            lines.append(command)
            lines.append("```")
            description = example.get("description")
            if description:
                lines.append(f"_Example:_ {description}")
            lines.append("")
    else:
        lines.append("```bash")
        lines.append(f"{app_name} {tool_def.name} --help")
        lines.append("```")
        lines.append("")
    return lines


def _command_error_table(meta: Any) -> list[str]:
    lines = ["#### Error Codes", "", "| Code | Condition | Recovery |", "|---|---|---|"]
    if not meta.error_codes:
        lines.append("| *(none declared)* | *(none)* | *(none)* |")
    else:
        for code, _message in sorted(meta.error_codes.items(), key=lambda item: item[0]):
            condition, recovery = _split_error_message(_message)
            lines.append(f"| {code} | {condition} | {recovery} |")
    lines.append("")
    return lines


def _output_schema_block(callback: Any) -> list[str]:
    schema = generate_tool_schema(callback, name=callback.__name__.replace("_", "-"))
    lines = ["#### Output Schema", ""]
    if schema.output_schema is None:
        lines.append("No output schema was declared.")
        lines.append("")
        return lines

    lines.extend(["```json", json.dumps(schema.output_schema, indent=2, sort_keys=True), "```", ""])
    return lines


class SkillGenerator:
    """Generate a complete v3-ready SKILL.md document from a Tooli app."""

    def __init__(
        self,
        app: Tooli,
        *,
        detail_level: DetailLevel = "auto",
        infer_workflows: bool = False,
    ) -> None:
        self.app = app
        self.detail_level = detail_level
        self.infer_workflows = infer_workflows

    @property
    def _tool_name(self) -> str:
        return self.app.info.name or "tooli-app"

    @property
    def _tool_help(self) -> str:
        return self._compose_frontmatter_description()

    @property
    def _tool_version(self) -> str:
        return getattr(self.app, "version", "1.0.0")

    def _compose_frontmatter_description(self) -> str:
        base = (self.app.info.help or "An agent-native CLI application.").strip()
        if not base:
            base = "An agent-native CLI application."

        trigger_text = ", ".join(self._triggers)
        anti_trigger_text = ", ".join(self._anti_triggers)

        parts = [base]
        if trigger_text:
            parts.append(f"Useful for: {trigger_text}.")
        if anti_trigger_text:
            parts.append(f"Avoid when: {anti_trigger_text}.")

        return " ".join(parts).strip()

    @property
    def _triggers(self) -> list[str]:
        explicit = list(getattr(self.app, "triggers", []) or [])
        if explicit:
            return explicit

        inferred: set[str] = set()
        for command in _collect_visible_commands(self.app):
            raw_name = command.name or ""
            if raw_name:
                inferred.add(raw_name.replace("-", " "))
            description = (command.help or command.callback.__doc__ or "").strip().replace("\n", " ")
            if description:
                inferred.update(_extract_tokens(description, limit=4))
        if inferred:
            return sorted(inferred)[:6]
        return ["command execution"]

    @property
    def _anti_triggers(self) -> list[str]:
        return list(getattr(self.app, "anti_triggers", []) or [])

    @property
    def _rules(self) -> list[str]:
        return list(getattr(self.app, "rules", []) or [])

    @property
    def _env_vars(self) -> dict[str, Mapping[str, Any]]:
        raw = getattr(self.app, "env_vars", None)
        return raw if isinstance(raw, dict) else {}

    def generate(self) -> str:
        lines: list[str] = []
        lines.extend(self._frontmatter())
        lines.extend(self._quick_reference())
        lines.extend(self._installation())
        lines.extend(self._global_flags())
        lines.extend(self._envelope())
        lines.extend(self._commands())
        lines.extend(self._error_catalog())
        lines.extend(self._workflows())
        lines.extend(self._critical_rules())
        return "\n".join(lines).rstrip() + "\n"

    def _frontmatter(self) -> list[str]:
        description = self._tool_help.replace('"', '\\"').replace("\n", " ")
        lines = [
            "---",
            f"name: {self._tool_name}",
            f"description: \"{description}\"",
            f"version: {self._tool_version}",
            "triggers:",
        ]
        for trigger in self._triggers:
            lines.append(f"  - {trigger}")
        if self._anti_triggers:
            lines.append("anti_triggers:")
            for trigger in self._anti_triggers:
                lines.append(f"  - {trigger}")
        lines.extend(["---", "", f"# {self._tool_name}"])
        return lines

    def _quick_reference(self) -> list[str]:
        lines = ["", "## Quick Reference", "", "| Task | Command |", "| --- | --- |"]
        for tool_def in _collect_visible_commands(self.app):
            for description, command in _command_reference_rows_for_tool(self._tool_name, tool_def):
                lines.append(f"| {description} | `{command}` |")
        lines.extend(
            [
                "| Get schema for a command | `{tool} <command> --schema` |".replace("{tool}", self._tool_name),
                "| Use JSON output for agents | `{tool} <command> --json` |".replace("{tool}", self._tool_name),
                "| Preview without executing | `{tool} <command> --dry-run` |".replace("{tool}", self._tool_name),
            ]
        )
        lines.append("")
        return lines

    def _installation(self) -> list[str]:
        lines = [
            "## Installation",
            "",
            "```bash",
            f"pip install {self._tool_name}",
            "```",
            "",
            "### Environment Variables",
            "",
            "| Variable | Required | Description |",
            "|---|---|---|",
        ]

        if self._env_vars:
            for name, info in self._env_vars.items():
                info_map = dict(info)
                required_for = info_map.get("required_for")
                required = "Yes" if required_for else "No"
                lines.append(f"| `{name}` | {required} | {info_map.get('description', '')} |")
        else:
            lines.append("| `TOOLI_OUTPUT` | No | Default output mode: `json`, `jsonl`, `text`, `plain` |")

        lines.extend(
            [
                "",
                "### Dependencies",
                "",
                "- Python ≥ 3.10",
                "- `typer`",
                "- `pydantic`",
                "",
            ]
        )
        return lines

    def _global_flags(self) -> list[str]:
        return [
            "## Global Flags",
            "",
            "| Flag | Effect |",
            "|---|---|",
            "| `--json` | Output as JSON envelope: `{\"ok\": bool, \"result\": ..., \"meta\": {...}}` |",
            "| `--jsonl` | Output JSONL stream for list outputs. |",
            "| `--plain` | Unformatted text output for pipelines. |",
            "| `--quiet` | Suppress non-essential output. |",
            "| `--dry-run` | Preview operations without mutating state. |",
            "| `--schema` | Print JSON schema for this command and exit. |",
            "| `--timeout N` | Maximum execution time in seconds. |",
            "| `--yes` | Skip interactive confirmation prompts. |",
            "| `--response-format concise|detailed` | Choose machine-readable response shape. |",
            "| `--help-agent` | Emit structured YAML help metadata. |",
            "| `--agent-manifest` | Emit machine-readable manifest. |",
            "",
        ]

    def _envelope(self) -> list[str]:
        return [
            "## Output Envelope Format",
            "",
            "All commands with `--json` return this shape:",
            "",
            "```json",
            '{',
            '  "ok": true,',
            '  "result": <command-result>,',
            '  "meta": {',
            f'    "tool": "{self._tool_name}",',
            f'    "version": "{self._tool_version}",',
            '    "duration_ms": 34,',
            '    "dry_run": false,',
            '    "truncated": false,',
            '    "next_cursor": null,',
            '    "warnings": []',
            "  }",
            "}",
            "```",
            "",
            "On failure:",
            "",
            "```json",
            '{',
            '  "ok": false,',
            '  "error": {',
            '    "code": "E3001",',
            '    "category": "state",',
            '    "message": "No files matched pattern",',
            '    "suggestion": {',
            '      "action": "retry_with_modified_input",',
            '      "fix": "Try a broader pattern.",',
            '      "example": "find-files \\"*.py\\" --root ./src"',
            "    },",
            '    "is_retryable": true',
            "  }",
            "}",
            "```",
            "",
            "Agents should always check `ok` first and respect `meta.truncated`.",
            "",
        ]

    def _commands(self) -> list[str]:
        tools = _collect_visible_commands(self.app)
        include_full = self.detail_level == "full" or (
            self.detail_level == "auto" and len(tools) <= _DEFAULT_MAX_COMMANDS_FOR_FULL
        )

        lines = ["## Commands", ""]
        if not include_full:
            lines.append("## Tier 2 summary (auto mode; use --detail-level full)")
            lines.append("")
            lines.extend(["| Command | Description |", "| --- | --- |"])
            for tool_def in tools:
                short_help = (tool_def.help or tool_def.callback.__doc__ or "").strip()
                summary = short_help.splitlines()[0] if short_help else tool_def.name
                lines.append(f"| `{tool_def.name}` | {summary} (run `{self._tool_name} {tool_def.name} --schema` for full details) |")
            lines.append("")
            return lines

        for tool_def in tools:
            callback = tool_def.callback
            help_text = (tool_def.help or callback.__doc__ or "").strip()
            short_help = help_text.splitlines()[0] if help_text else tool_def.name
            meta = get_command_meta(callback)

            lines.extend([f"### `{tool_def.name}`", "", short_help, ""])
            behavior = _annotation_labels(callback)
            lines.append(f"**Behavior**: `{', '.join(behavior) or 'unspecified'}`")
            if meta.cost_hint is not None:
                lines.append(f"**Cost Hint**: `{meta.cost_hint}`")
            if meta.deprecated:
                lines.append("**Deprecated**: `true`")
                if meta.deprecated_message:
                    lines.append(f"**Deprecation Message**: {meta.deprecated_message}")
            lines.append("")

            params = _command_signature_params(callback)
            lines.extend(
                [
                    "#### Parameters",
                    "",
                    "| Parameter | Type | Required | Default | Description |",
                    "|---|---|---|---|---|",
                ]
            )
            for name, annotation, default, description in params:
                lines.append(
                    "| "
                    f"`{name}` | "
                    f"`${_readable_type(annotation)}` | "
                    f"{'Yes' if _is_required_param(default) else 'No'} | "
                    f"`{_normalize_default(default)}` | "
                    f"{description or '--'} |"
                )
            lines.append("")

            lines.extend(_output_schema_block(callback))
            lines.extend(_command_examples(self._tool_name, tool_def))
            lines.extend(_command_error_table(meta))

        lines.append("")
        return lines

    def _error_catalog(self) -> list[str]:
        lines = [
            "## Error Catalog",
            "",
            "| Code | Category | Command | Condition | Recovery |",
            "|---|---|---|---|---|",
        ]
        rows: list[tuple[str, str, str, str, str]] = []

        for tool_def in _collect_visible_commands(self.app):
            meta = get_command_meta(tool_def.callback)
            for code, message in sorted(meta.error_codes.items(), key=lambda item: item[0]):
                condition, recovery = _split_error_message(message)
                rows.append((code, _error_category(code), tool_def.name, condition, recovery))

        if not rows:
            lines.append("| *(none declared)* | (global) | *(none)* | *(none)* | *(none)* |")
        else:
            for code, category, command, condition, recovery in rows:
                lines.append(f"| {code} | {category} | {command} | {condition} | {recovery} |")

        lines.extend(
            [
                "",
                "## Exit Codes",
                "",
                "| Code | Meaning |",
                "|---|---|",
                "| 0 | Success |",
                "| 2 | Invalid usage / validation error |",
                "| 10 | Not found / state error |",
                "| 30 | Permission denied |",
                "| 50 | Timeout / temporary external delay |",
                "| 70 | Internal or runtime error |",
                "| 101 | Human handoff required |",
                "",
            ]
        )
        return lines

    def _workflow_rows(self, workflow: Mapping[str, Any], explicit: bool) -> list[str]:
        name = str(workflow.get("name", "Workflow"))
        description = str(workflow.get("description", ""))
        lines = [f"### {name}", ""]
        if description:
            lines.append(description)
            lines.append("")
        lines.append("```bash")
        for step in workflow.get("steps", []):
            if isinstance(step, Mapping):
                command = step.get("command", "").strip()
                if not command:
                    continue
                flags = step.get("flags", [])
                if isinstance(flags, (list, tuple)):
                    command = f"{command} {' '.join(str(flag) for flag in flags)}".rstrip()
                elif flags:
                    command = f"{command} {flags}"
                lines.append(f"{self._tool_name} {command}".strip())
                note = step.get("note")
                if note:
                    lines.append(f"# {note}")
            elif isinstance(step, str):
                lines.append(f"{self._tool_name} {step}".strip())
        if explicit:
            lines.append("# Declarative workflow")
        lines.append("```")
        lines.append("")
        return lines

    def _workflows(self) -> list[str]:
        explicit = list(getattr(self.app, "workflows", []) or [])
        inferred = self._infer_workflows() if self.infer_workflows else []
        lines = ["## Workflow Patterns", ""]
        if not explicit and not inferred:
            lines.extend(["No workflows were declared.", "Run `generate-skill --infer-workflows` for inferred patterns.", ""])
            return lines

        for workflow in explicit:
            if isinstance(workflow, Mapping):
                lines.extend(self._workflow_rows(workflow, explicit=True))

        if inferred:
            lines.append("### Inferred Workflows")
            lines.append("")
            for name, commands in inferred:
                lines.append(f"### {name}")
                lines.extend(["", "```bash"])
                lines.extend(commands)
                lines.extend(["```", ""])

        return lines

    def _infer_workflows(self) -> list[tuple[str, list[str]]]:
        tools = _collect_visible_commands(self.app)
        if len(tools) < 2:
            return []

        workflows: list[tuple[str, list[str]]] = []
        ro_commands = [tool for tool in tools if "read-only" in _annotation_labels(tool.callback)]
        destructive_commands = [tool for tool in tools if "destructive" in _annotation_labels(tool.callback)]

        for ro in ro_commands:
            for destructive in destructive_commands:
                if not ro.name or not destructive.name:
                    continue
                name = f"{ro.name} then {destructive.name}"
                lines = [
                    f"{self._tool_name} {ro.name} --json",
                    f"{self._tool_name} {destructive.name} --dry-run --json",
                    f"{self._tool_name} {destructive.name} --json",
                ]
                workflows.append((name, lines))

        param_map = {
            tool.name or "": [name for name, *_rest in _command_signature_params(tool.callback)]
            for tool in tools
        }
        for left_name, left_params in param_map.items():
            if not left_name:
                continue
            for right_name, right_params in param_map.items():
                if not right_name or right_name == left_name:
                    continue
                shared = set(left_params) & set(right_params)
                if shared:
                    label = f"Search then process: {left_name} -> {right_name}"
                    line = f"{self._tool_name} {left_name} --json | {self._tool_name} {right_name} --json"
                    workflows.append((label, [line]))
                    break

        for tool in tools:
            callback = tool.callback
            meta = get_command_meta(callback)
            if meta.paginated and tool.name:
                line = f"{self._tool_name} {tool.name} --json --limit 20"
                line2 = f"{self._tool_name} {tool.name} --json --cursor <next_cursor>"
                workflows.append((f"Paginate {tool.name}", [line, line2]))

            for param_name, annotation, _default, _ in _command_signature_params(callback):
                if _is_stdin_or_annotation(annotation) and tool.name:
                    line = f'echo "..." | {self._tool_name} {tool.name} --json --{param_name.replace("_", "-")}'
                    workflows.append((f"Pipe into {tool.name}", [line]))
                    break

        deduped: list[tuple[str, list[str]]] = []
        seen: set[str] = set()
        for name, commands in workflows:
            key = name + "|" + "|".join(commands)
            if key in seen:
                continue
            seen.add(key)
            deduped.append((name, commands))

        return deduped[:12]

    def _critical_rules(self) -> list[str]:
        rules = [
            "Always use `--json` when invoking from an agent.",
            "Always check `ok` before reading `result`.",
            "Paths are relative to CWD unless `--root` is used.",
            "Use `meta.dry_run` to verify whether dry-run mode was honored.",
            "If `meta.truncated` is `true`, pass `--cursor <next_cursor>` on the next call.",
        ]

        for rule in self._rules:
            if rule not in rules:
                rules.append(rule)

        lines = ["## Critical Rules", ""]
        lines.extend(f"- {rule}" for rule in rules)
        lines.append("")
        lines.extend(["## End", "Generated by Tooli v3.0."])
        return lines


def generate_skill_md(
    app: Tooli,
    *,
    detail_level: DetailLevel = "auto",
    infer_workflows: bool = False,
) -> str:
    """Backward compatible function-style API for skill generation."""
    return SkillGenerator(app, detail_level=detail_level, infer_workflows=infer_workflows).generate()


def validate_skill_doc(content: str) -> dict[str, Any]:
    """Validate core SKILL.md structure generated by Tooli."""
    issues: list[dict[str, Any]] = []
    if not content.startswith("---\n"):
        issues.append({"message": "Missing frontmatter opening marker."})
    else:
        frontmatter_match = re.search(r"^---\n.*?\n---\n", content, flags=re.S)
        if not frontmatter_match:
            issues.append({"message": "Malformed or unclosed frontmatter block."})

    required_sections = [
        "## Quick Reference",
        "## Installation",
        "## Global Flags",
        "## Output Envelope Format",
        "## Commands",
        "## Error Catalog",
        "## Workflow Patterns",
        "## Critical Rules",
    ]
    for section in required_sections:
        if section not in content:
            issues.append({"message": f"Missing required section: {section}."})

    return {"valid": len(issues) == 0, "issues": issues}
