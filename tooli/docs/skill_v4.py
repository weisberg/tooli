"""v4 SKILL.md generator — task-oriented, composition-aware agent skill docs."""

from __future__ import annotations

import inspect
import json
import re
from collections import defaultdict
from collections.abc import Mapping  # noqa: TC003
from typing import Any, Literal, get_args, get_origin

from tooli.command_meta import get_command_meta
from tooli.pipes import pipe_contracts_compatible
from tooli.schema import generate_tool_schema

DetailLevel = Literal["auto", "full", "summary"]
TargetFormat = Literal["generic-skill", "claude-skill", "claude-code"]

_DEFAULT_MAX_COMMANDS_FOR_FULL = 20


def estimate_skill_tokens(content: str, model: str = "o200k_base") -> int:
    """Estimate token count for generated documentation."""
    if not content:
        return 0
    try:
        import tiktoken  # type: ignore[import-not-found]

        encoder = tiktoken.get_encoding(model)
        return len(encoder.encode(content))
    except Exception:
        return len(content.split())


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

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
            return f"tuple[{', '.join(_readable_type(a) for a in args)}]"
        return "tuple"
    if get_origin(annotation) is dict:
        args = get_args(annotation)
        if len(args) == 2:
            return f"dict[{_readable_type(args[0])}, {_readable_type(args[1])}]"
        return "dict"
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        if args:
            return f"{_simple_type_name(origin)}[{', '.join(_readable_type(a) for a in args)}]"
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
        return "\u2014"
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


def _collect_visible_commands(app: Any) -> list[Any]:
    return [tool_def for tool_def in app.get_tools() if not tool_def.hidden]


def _extract_tokens(text: str, limit: int = 3) -> list[str]:
    if not text:
        return []
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", text.lower())
    return [w for w in words[:limit]]


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


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class SkillV4Generator:
    """Generate a complete v4-ready SKILL.md document from a Tooli app.

    Differences from v3:
    - Task-oriented grouping via ``task_group``
    - Per-command "When to use" prose from ``when_to_use`` or auto-synthesis
    - Inline "If Something Goes Wrong" from ``recovery_playbooks``
    - Expected output rendering from ``expected_outputs`` / ``output_example``
    - Enhanced trigger synthesis with template
    - Composition Patterns from pipe contracts
    - Section order matches PRD section 7
    """

    def __init__(
        self,
        app: Any,
        *,
        detail_level: DetailLevel = "auto",
        infer_workflows: bool = False,
        target: TargetFormat = "generic-skill",
    ) -> None:
        self.app = app
        self.detail_level = detail_level
        self.infer_workflows = infer_workflows
        self.target = target

    @property
    def _tool_name(self) -> str:
        return self.app.info.name or "tooli-app"

    @property
    def _tool_version(self) -> str:
        return getattr(self.app, "version", "1.0.0")

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

    def _compose_frontmatter_description(self) -> str:
        base = (self.app.info.help or "An agent-native CLI application.").strip()
        if not base:
            base = "An agent-native CLI application."
        triggers = self._triggers
        anti_triggers = self._anti_triggers
        trigger_text = ", ".join(triggers)
        anti_trigger_text = ", ".join(anti_triggers)
        also_clause = ""
        if trigger_text:
            also_clause = f" Triggers include: {trigger_text}."
        parts = [f"Use this skill whenever {base.rstrip('.')}.{also_clause}"]
        if anti_trigger_text:
            parts.append(f"Do NOT use for {anti_trigger_text}.")
        return " ".join(parts).strip()

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def generate(self) -> str:
        lines: list[str] = []
        lines.extend(self._frontmatter())
        lines.extend(self._quick_reference())
        lines.extend(self._installation())
        lines.extend(self._commands())
        lines.extend(self._composition_patterns())
        lines.extend(self._global_flags())
        lines.extend(self._envelope())
        lines.extend(self._error_catalog())
        lines.extend(self._critical_rules())
        return "\n".join(lines).rstrip() + "\n"

    def _frontmatter(self) -> list[str]:
        description = self._compose_frontmatter_description().replace('"', '\\"').replace("\n", " ")
        lines = [
            "---",
            f"name: {self._tool_name}",
            f'description: "{description}"',
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
            for description, command in self._reference_rows(tool_def):
                lines.append(f"| {description} | `{command}` |")
        lines.extend([
            f"| Get schema for a command | `{self._tool_name} <command> --schema` |",
            f"| Use JSON output for agents | `{self._tool_name} <command> --json` |",
            f"| Preview without executing | `{self._tool_name} <command> --dry-run` |",
        ])
        lines.append("")
        return lines

    def _reference_rows(self, tool_def: Any) -> list[tuple[str, str]]:
        callback = tool_def.callback
        meta = get_command_meta(callback)
        if meta.examples:
            raw_args = meta.examples[0].get("args", [])
            if isinstance(raw_args, list):
                command = " ".join([self._tool_name, tool_def.name] + [str(a) for a in raw_args if a is not None])
                label = meta.examples[0].get("description") or tool_def.name
                return [(label, command)]
        required_args = [
            f"<{name}>"
            for name, _ann, default, _desc in _command_signature_params(callback)
            if _is_required_param(default)
        ]
        description = tool_def.help or callback.__doc__ or tool_def.name
        label = " ".join(line.strip() for line in description.splitlines() if line.strip()) or str(tool_def.name)
        command = f"{self._tool_name} {tool_def.name}" + (" " + " ".join(required_args) if required_args else "")
        return [(label, command)]

    def _installation(self) -> list[str]:
        lines = [
            "## Installation",
            "",
            "```bash",
            f"pip install {self._tool_name}",
            "```",
            "",
        ]
        if self._env_vars:
            lines.extend([
                "### Environment Variables",
                "",
                "| Variable | Required | Description |",
                "|---|---|---|",
            ])
            for name, info in self._env_vars.items():
                info_map = dict(info)
                required_for = info_map.get("required_for")
                required = "Yes" if required_for else "No"
                lines.append(f"| `{name}` | {required} | {info_map.get('description', '')} |")
            lines.append("")
        return lines

    def _commands(self) -> list[str]:
        tools = _collect_visible_commands(self.app)
        include_full = self.detail_level == "full" or (
            self.detail_level == "auto" and len(tools) <= _DEFAULT_MAX_COMMANDS_FOR_FULL
        )

        lines = ["## Commands", ""]
        if not include_full:
            lines.extend(["| Command | Description |", "| --- | --- |"])
            for tool_def in tools:
                short_help = (tool_def.help or tool_def.callback.__doc__ or "").strip()
                summary = short_help.splitlines()[0] if short_help else tool_def.name
                lines.append(f"| `{tool_def.name}` | {summary} (run `{self._tool_name} {tool_def.name} --schema` for full details) |")
            lines.append("")
            return lines

        # Group commands by task_group
        grouped: dict[str, list[Any]] = defaultdict(list)
        for tool_def in tools:
            meta = get_command_meta(tool_def.callback)
            group = meta.task_group or "General"
            grouped[group].append(tool_def)

        # Emit groups (non-General first, then General)
        group_order = [g for g in grouped if g != "General"]
        if "General" in grouped:
            group_order.append("General")

        for group_name in group_order:
            if len(grouped) > 1:
                lines.extend([f"### {group_name}", ""])
            for tool_def in grouped[group_name]:
                lines.extend(self._command_section(tool_def))

        lines.append("")
        return lines

    def _command_section(self, tool_def: Any) -> list[str]:
        callback = tool_def.callback
        help_text = (tool_def.help or callback.__doc__ or "").strip()
        short_help = help_text.splitlines()[0] if help_text else tool_def.name
        meta = get_command_meta(callback)

        heading_level = "###" if self._has_multiple_groups() else "###"
        if self._has_multiple_groups():
            heading_level = "####"
        lines = [f"{heading_level} `{tool_def.name}`", "", short_help, ""]

        # When to use
        when_to_use = self._synthesize_when_to_use(tool_def, meta)
        if when_to_use:
            lines.extend([f"**When to use**: {when_to_use}", ""])

        # Behavior + metadata
        behavior = _annotation_labels(callback)
        lines.append(f"**Behavior**: `{', '.join(behavior) or 'unspecified'}`")
        if meta.cost_hint is not None:
            lines.append(f"**Cost Hint**: `{meta.cost_hint}`")
        if meta.deprecated:
            lines.append("**Deprecated**: `true`")
            if meta.deprecated_message:
                lines.append(f"**Deprecation Message**: {meta.deprecated_message}")
        lines.append("")

        # Parameters
        params = _command_signature_params(callback)
        lines.extend([
            f"{heading_level}# Parameters",
            "",
            "| Parameter | Type | Required | Default | Description |",
            "|---|---|---|---|---|",
        ])
        for name, annotation, default, description in params:
            desc = description or "\u2014"
            lines.append(
                f"| `{name}` | `${_readable_type(annotation)}` | "
                f"{'Yes' if _is_required_param(default) else 'No'} | "
                f"`{_normalize_default(default)}` | {desc} |"
            )
        lines.append("")

        # Output schema
        lines.extend(self._output_schema_block(callback))

        # Examples with expected output
        lines.extend(self._command_examples(tool_def, meta))

        # If Something Goes Wrong
        lines.extend(self._error_recovery_section(tool_def, meta, heading_level))

        return lines

    def _has_multiple_groups(self) -> bool:
        tools = _collect_visible_commands(self.app)
        groups: set[str] = set()
        for tool_def in tools:
            meta = get_command_meta(tool_def.callback)
            groups.add(meta.task_group or "General")
        return len(groups) > 1

    def _synthesize_when_to_use(self, tool_def: Any, meta: Any) -> str:
        if meta.when_to_use:
            return meta.when_to_use
        # Auto-synthesize from docstring + annotations
        help_text = (tool_def.help or tool_def.callback.__doc__ or "").strip()
        if not help_text:
            return ""
        first_line = help_text.splitlines()[0].rstrip(".")
        labels = _annotation_labels(tool_def.callback)
        if labels:
            return f"{first_line}. This command is {', '.join(labels)}."
        return f"{first_line}."

    def _output_schema_block(self, callback: Any) -> list[str]:
        schema = generate_tool_schema(callback, name=callback.__name__.replace("_", "-"))
        lines = ["#### Output Schema", ""]
        if schema.output_schema is None:
            lines.append("No output schema was declared.")
            lines.append("")
            return lines
        lines.extend(["```json", json.dumps(schema.output_schema, indent=2, sort_keys=True), "```", ""])
        return lines

    def _command_examples(self, tool_def: Any, meta: Any) -> list[str]:
        lines = ["#### Examples", ""]
        examples = meta.examples
        if examples:
            for i, example in enumerate(examples):
                args = example.get("args")
                if isinstance(args, list):
                    arg_text = " ".join(str(a) for a in args if a is not None)
                else:
                    arg_text = ""
                command = f"{self._tool_name} {tool_def.name} {arg_text}".strip()
                lines.extend(["```bash", command, "```"])
                description = example.get("description")
                if description:
                    lines.append(f"_Example:_ {description}")
                # Render expected output
                expected = None
                if i < len(meta.expected_outputs):
                    expected = meta.expected_outputs[i]
                elif meta.output_example is not None and i == 0:
                    expected = meta.output_example
                if expected is not None:
                    lines.extend(["", "Expected output:", "", "```json", json.dumps(expected, indent=2, sort_keys=True), "```"])
                lines.append("")
        else:
            lines.extend(["```bash", f"{self._tool_name} {tool_def.name} --help", "```", ""])
        return lines

    def _error_recovery_section(self, tool_def: Any, meta: Any, heading_level: str) -> list[str]:
        has_playbooks = bool(meta.recovery_playbooks)
        has_error_codes = bool(meta.error_codes)
        if not has_playbooks and not has_error_codes:
            return []

        lines = [f"{heading_level}# If Something Goes Wrong", ""]

        if has_playbooks:
            for error_key, steps in meta.recovery_playbooks.items():
                lines.append(f"**{error_key}**:")
                for step in steps:
                    lines.append(f"  1. {step}")
                lines.append("")

        if has_error_codes:
            lines.extend(["| Code | Condition | Recovery |", "|---|---|---|"])
            for code, message in sorted(meta.error_codes.items(), key=lambda item: item[0]):
                condition, recovery = _split_error_message(message)
                lines.append(f"| {code} | {condition} | {recovery} |")
            lines.append("")

        return lines

    def _composition_patterns(self) -> list[str]:
        lines = ["## Composition Patterns", ""]
        patterns = self._infer_compositions()
        if not patterns:
            lines.extend(["No composition patterns detected.", ""])
            return lines
        for name, commands in patterns:
            lines.extend([f"### {name}", "", "```bash"])
            lines.extend(commands)
            lines.extend(["```", ""])
        return lines

    def _infer_compositions(self) -> list[tuple[str, list[str]]]:
        tools = _collect_visible_commands(self.app)
        if len(tools) < 2:
            return []

        patterns: list[tuple[str, list[str]]] = []

        # 1) Pipe contract matching: output→input
        for left in tools:
            left_meta = get_command_meta(left.callback)
            for right in tools:
                if left.name == right.name:
                    continue
                right_meta = get_command_meta(right.callback)
                if pipe_contracts_compatible(left_meta.pipe_output, right_meta.pipe_input):
                    label = f"Pipe {left.name} into {right.name}"
                    line = f"{self._tool_name} {left.name} --json | {self._tool_name} {right.name} --json"
                    patterns.append((label, [line]))

        # 2) ReadOnly → Destructive preview pairs
        ro_commands = [t for t in tools if "read-only" in _annotation_labels(t.callback)]
        destructive_commands = [t for t in tools if "destructive" in _annotation_labels(t.callback)]
        for ro in ro_commands:
            for dest in destructive_commands:
                if not ro.name or not dest.name:
                    continue
                label = f"Preview then execute: {ro.name} \u2192 {dest.name}"
                cmds = [
                    f"{self._tool_name} {ro.name} --json",
                    f"{self._tool_name} {dest.name} --dry-run --json",
                    f"{self._tool_name} {dest.name} --json",
                ]
                patterns.append((label, cmds))

        # 3) Dry-run patterns
        for tool_def in tools:
            meta = get_command_meta(tool_def.callback)
            if meta.supports_dry_run and "destructive" in _annotation_labels(tool_def.callback):
                label = f"Safe execution: {tool_def.name}"
                cmds = [
                    f"{self._tool_name} {tool_def.name} --dry-run --json",
                    "# Review output, then:",
                    f"{self._tool_name} {tool_def.name} --json",
                ]
                patterns.append((label, cmds))

        # 4) Pagination chains
        for tool_def in tools:
            meta = get_command_meta(tool_def.callback)
            if meta.paginated and tool_def.name:
                cmds = [
                    f"{self._tool_name} {tool_def.name} --json --limit 20",
                    f"{self._tool_name} {tool_def.name} --json --cursor <next_cursor>",
                ]
                patterns.append((f"Paginate {tool_def.name}", cmds))

        # 5) Inferred workflows if requested
        if self.infer_workflows:
            patterns.extend(self._infer_piped_workflows(tools))

        # Deduplicate
        deduped: list[tuple[str, list[str]]] = []
        seen: set[str] = set()
        for name, cmds in patterns:
            key = name + "|" + "|".join(cmds)
            if key in seen:
                continue
            seen.add(key)
            deduped.append((name, cmds))

        return deduped[:12]

    def _infer_piped_workflows(self, tools: list[Any]) -> list[tuple[str, list[str]]]:
        patterns: list[tuple[str, list[str]]] = []
        for tool_def in tools:
            callback = tool_def.callback
            for param_name, annotation, _default, _ in _command_signature_params(callback):
                if _is_stdin_or_annotation(annotation) and tool_def.name:
                    line = f'echo "..." | {self._tool_name} {tool_def.name} --json --{param_name.replace("_", "-")}'
                    patterns.append((f"Pipe into {tool_def.name}", [line]))
                    break
        return patterns

    def _global_flags(self) -> list[str]:
        lines = [
            "## Global Flags",
            "",
            "| Flag | Effect |",
            "|---|---|",
            '| `--json` | Output as JSON envelope: `{"ok": bool, "result": ..., "meta": {...}}` |',
            "| `--jsonl` | Output JSONL stream for list outputs. |",
            "| `--plain` | Unformatted text output for pipelines. |",
            "| `--quiet` | Suppress non-essential output. |",
            "| `--dry-run` | Preview operations without mutating state. |",
            "| `--schema` | Print JSON schema for this command and exit. |",
            "| `--timeout N` | Maximum execution time in seconds. |",
            "| `--yes` | Skip interactive confirmation prompts. |",
            "| `--response-format concise\\|detailed` | Choose machine-readable response shape. |",
            "| `--help-agent` | Emit structured YAML help metadata. |",
            "| `--agent-manifest` | Emit machine-readable manifest. |",
            "| `--agent-bootstrap` | Generate deployable SKILL.md and exit. |",
            "",
        ]
        return lines

    def _envelope(self) -> list[str]:
        return [
            "## Output Format",
            "",
            "All commands with `--json` return this shape:",
            "",
            "```json",
            "{",
            '  "ok": true,',
            '  "result": "<command-result>",',
            "  \"meta\": {",
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
            "On failure, `ok` is `false` and an `error` object is present with `code`, `category`, `message`, and optional `suggestion`.",
            "",
        ]

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

        lines.extend([
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
        ])
        return lines

    def _critical_rules(self) -> list[str]:
        rules = [
            "Always use `--json` when invoking from an agent.",
            "Always check `ok` before reading `result`.",
            "Paths are relative to CWD unless `--root` is used.",
            "Use `meta.dry_run` to verify whether dry-run mode was honored.",
            "If `meta.truncated` is `true`, pass `--cursor <next_cursor>` on the next call.",
        ]
        if self.target == "claude-code":
            rules.append("Use Bash tool to invoke CLI commands.")
        for rule in self._rules:
            if rule not in rules:
                rules.append(rule)

        lines = ["## Critical Rules", ""]
        lines.extend(f"- {rule}" for rule in rules)
        lines.append("")
        lines.extend(["## End", "Generated by Tooli v4.0."])
        return lines

    def generate_skill_package(self, output_dir: str) -> list[str]:
        """Produce SKILL.md, install.sh, verify.sh in the given directory."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        skill_content = self.generate()
        skill_path = os.path.join(output_dir, "SKILL.md")
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(skill_content)

        install_path = os.path.join(output_dir, "install.sh")
        with open(install_path, "w", encoding="utf-8") as f:
            f.write(f"#!/usr/bin/env bash\npip install {self._tool_name}\n")

        verify_path = os.path.join(output_dir, "verify.sh")
        with open(verify_path, "w", encoding="utf-8") as f:
            f.write(f"#!/usr/bin/env bash\n{self._tool_name} --help\n")

        return [skill_path, install_path, verify_path]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_skill_md(
    app: Any,
    *,
    detail_level: DetailLevel = "auto",
    infer_workflows: bool = False,
    target: TargetFormat = "generic-skill",
) -> str:
    """Function-style API for v4 skill generation."""
    return SkillV4Generator(
        app,
        detail_level=detail_level,
        infer_workflows=infer_workflows,
        target=target,
    ).generate()


def validate_skill_doc(content: str) -> dict[str, Any]:
    """Validate core SKILL.md structure generated by Tooli v4."""
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
        "## Commands",
        "## Composition Patterns",
        "## Global Flags",
        "## Output Format",
        "## Error Catalog",
        "## Critical Rules",
    ]
    for section in required_sections:
        if section not in content:
            issues.append({"message": f"Missing required section: {section}."})

    return {"valid": len(issues) == 0, "issues": issues}
