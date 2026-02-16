"""Core Tooli application class extending Typer."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable  # noqa: TC003
from pathlib import Path  # noqa: TC003
from typing import Annotated, Any, get_args, get_origin, get_type_hints

import click  # noqa: TC002
import typer
from typer.main import TyperGroup  # type: ignore[attr-defined]

from tooli.auth import AuthContext
from tooli.command import TooliCommand, _emit_parser_error, _is_agent_mode
from tooli.command_meta import CommandMeta, PromptMeta, ResourceMeta, get_command_meta
from tooli.eval.recorder import build_invocation_recorder
from tooli.input import SecretInput, is_secret_input
from tooli.providers.local import LocalProvider
from tooli.security.policy import resolve_security_policy
from tooli.telemetry_pipeline import build_telemetry_pipeline
from tooli.transforms import ToolDef, Transform  # noqa: TC001
from tooli.versioning import compare_versions


class TooliGroup(TyperGroup):
    """Command group with machine-mode parser error envelopes."""

    def _estimate_app_version(self) -> str:
        for command in self.commands.values():
            callback = getattr(command, "callback", None)
            meta = get_command_meta(callback)
            if meta.app_version:
                return str(meta.app_version)
        return "0.0.0"

    def main(  # type: ignore[override]
        self,
        args: list[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> Any:
        start_time = time.perf_counter()
        try:
            return super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                windows_expand_args=windows_expand_args,
                **extra,
            )
        except click.UsageError as exc:
            if not standalone_mode:
                raise
            if not _is_agent_mode():
                exc.show()
                raise SystemExit(2) from exc
            _emit_parser_error(
                exc.format_message(),
                command_name=self.name or "tooli",
                app_version=self._estimate_app_version(),
                start_time=start_time,
                code="E1001",
            )
            raise SystemExit(2) from exc
        except click.ClickException as exc:
            if not standalone_mode:
                raise
            if not _is_agent_mode():
                exc.show()
                raise SystemExit(2) from exc
            _emit_parser_error(
                exc.format_message(),
                command_name=self.name or "tooli",
                app_version=self._estimate_app_version(),
                start_time=start_time,
                code="E1002",
            )
            raise SystemExit(2) from exc


class Tooli(typer.Typer):
    """Agent-native CLI framework extending Typer.

    Tooli wraps Typer to produce CLI tools that are simultaneously
    human-friendly and machine-consumable by AI agents. The public API
    is Tooli-native — Typer is an implementation detail.
    """

    def __init__(
        self,
        *args: Any,
        version: str = "0.0.0",
        default_output: str = "auto",
        mcp_transport: str = "stdio",
        skill_auto_generate: bool = False,
        permissions: dict[str, str] | None = None,
        telemetry: bool | None = None,
        telemetry_endpoint: str | None = None,
        telemetry_storage_dir: Path | None = None,
        telemetry_retention_days: int = 30,
        security_policy: str | None = None,
        auth_scopes: list[str] | None = None,
        record: bool | str | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("cls", TooliGroup)
        super().__init__(*args, **kwargs)

        # Tooli-specific configuration
        self.version = version
        self.default_output = default_output
        self.mcp_transport = mcp_transport
        self.skill_auto_generate = skill_auto_generate
        self.permissions = permissions or {}
        self.security_policy = resolve_security_policy(security_policy)
        self.auth_context = AuthContext.from_env(programmatic_scopes=auth_scopes)
        self.telemetry = telemetry
        self.telemetry_endpoint = telemetry_endpoint
        self.telemetry_storage_dir = telemetry_storage_dir
        self.telemetry_retention_days = telemetry_retention_days
        self.telemetry_pipeline = build_telemetry_pipeline(
            app_name=self.info.name or "tooli",
            telemetry=telemetry,
            endpoint=telemetry_endpoint,
            storage_dir=telemetry_storage_dir,
            retention_days=telemetry_retention_days,
        )
        self.invocation_recorder = build_invocation_recorder(record=record)

        self._versioned_commands_latest: dict[str, str] = {}
        self._providers: list[Any] = [LocalProvider(self)]
        self._transforms: list[Transform] = []
        self._resources: list[tuple[Callable[..., Any], ResourceMeta]] = []
        self._prompts: list[tuple[Callable[..., Any], PromptMeta]] = []

        # Register built-in commands
        self._register_builtins()

    def add_provider(self, provider: Any) -> None:
        """Register an additional tool provider."""
        self._providers.append(provider)

    def with_transforms(self, *transforms: Transform) -> Tooli:
        """Return a new Tooli instance (view) with transforms applied."""
        import copy
        # This is a shallow copy for the "view"
        view = copy.copy(self)
        view._transforms = list(self._transforms) + list(transforms)
        return view

    def get_tools(self) -> list[ToolDef]:
        """Return all tools from all providers, with transforms applied."""
        tools: list[ToolDef] = []
        for provider in self._providers:
            tools.extend(provider.get_tools())

        for transform in self._transforms:
            tools = transform.apply(tools)

        return tools

    def get_resources(self) -> list[tuple[Callable[..., Any], ResourceMeta]]:
        """Return registered MCP resource callbacks."""
        return list(self._resources)

    def get_prompts(self) -> list[tuple[Callable[..., Any], PromptMeta]]:
        """Return registered MCP prompt callbacks."""
        return list(self._prompts)

    def list_commands(self, ctx: click.Context | None = None) -> list[str]:
        """Override click help output to use transformed command names."""
        del ctx
        return sorted(tool.name for tool in self.get_tools() if not tool.hidden)

    def resource(
        self,
        uri: str,
        *,
        description: str | None = None,
        mime_type: str | None = None,
        name: str | None = None,
        hidden: bool = False,
        tags: list[str] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an MCP resource callback."""

        def _wrap(callback: Callable[..., Any]) -> Callable[..., Any]:
            resource_meta = ResourceMeta(
                uri=uri,
                description=description,
                mime_type=mime_type,
                name=name or callback.__name__,
                hidden=hidden,
                tags=tags or [],
            )
            callback.__tooli_resource_meta__ = resource_meta  # type: ignore[attr-defined]
            self._resources.append((callback, resource_meta))
            return callback

        return _wrap

    def prompt(
        self,
        name: str,
        *,
        description: str | None = None,
        hidden: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an MCP prompt callback."""

        def _wrap(callback: Callable[..., Any]) -> Callable[..., Any]:
            prompt_meta = PromptMeta(name=name, description=description, hidden=hidden)
            callback.__tooli_prompt_meta__ = prompt_meta  # type: ignore[attr-defined]
            self._prompts.append((callback, prompt_meta))
            return callback

        return _wrap

    def _register_builtins(self) -> None:
        @self.command(name="generate-skill", hidden=True)  # type: ignore[untyped-decorator]
        def generate_skill(
            output: str = typer.Option("SKILL.md", help="Output file path"),
        ) -> None:
            """Generate SKILL.md for this application."""
            from tooli.docs.skill import generate_skill_md

            content = generate_skill_md(self)
            with open(output, "w") as f:
                f.write(content)
            import click

            click.echo(f"Generated {output}")

        # MCP group
        mcp_app = typer.Typer(name="mcp", help="MCP server utilities", hidden=True)
        self.add_typer(mcp_app)

        @mcp_app.command(name="export")
        def mcp_export(
            defer_loading: bool = typer.Option(False, help="Expose discovery-focused MCP tools only."),
            include_resources: bool = typer.Option(False, help="Include resources and prompts in the output."),
        ) -> None:
            """Export MCP tool definitions as JSON."""
            import json

            import click

            from tooli.mcp.export import export_mcp_tools

            payload = export_mcp_tools(self, defer_loading=defer_loading, include_resources=include_resources)
            click.echo(json.dumps(payload, indent=2))

        @mcp_app.command(name="serve")
        def mcp_serve(
            transport: str = typer.Option("stdio", help="MCP transport: stdio|http|sse"),
            host: str = typer.Option("localhost", help="HTTP/SSE host"),
            port: int = typer.Option(8080, help="HTTP/SSE port"),
            defer_loading: bool = typer.Option(False, help="Expose only discovery tools and run-tool wrapper."),
        ) -> None:
            """Run the application as an MCP server."""
            from tooli.mcp.server import serve_mcp

            serve_mcp(self, transport=transport, host=host, port=port, defer_loading=defer_loading)

        # Docs group
        docs_app = typer.Typer(name="docs", help="Documentation generation", hidden=True)
        self.add_typer(docs_app)

        @docs_app.command(name="llms")
        def docs_llms() -> None:
            """Emit llms.txt and llms-full.txt."""
            from tooli.docs.llms_txt import generate_llms_full_txt, generate_llms_txt

            with open("llms.txt", "w") as f:
                f.write(generate_llms_txt(self))
            with open("llms-full.txt", "w") as f:
                f.write(generate_llms_full_txt(self))

            import click

            click.echo("Generated llms.txt and llms-full.txt")

        @docs_app.command(name="man")
        def docs_man() -> None:
            """Generate a Unix man page."""
            from tooli.docs.man import generate_man_page

            content = generate_man_page(self)
            name = self.info.name or "tooli-app"
            filename = f"{name}.1"
            with open(filename, "w") as f:
                f.write(content)

            import click

            click.echo(f"Generated {filename}")

        # API group
        api_app = typer.Typer(name="api", help="HTTP API utilities (experimental)", hidden=True)
        self.add_typer(api_app)

        @api_app.command(name="export-openapi")
        def api_export_openapi() -> None:
            """Export OpenAPI 3.1.0 schema as JSON (experimental)."""
            import json

            import click

            from tooli.api.openapi import generate_openapi_schema

            schema = generate_openapi_schema(self)
            click.echo(json.dumps(schema, indent=2))

        @api_app.command(name="serve")
        def api_serve(
            host: str = typer.Option("localhost", help="HTTP host"),
            port: int = typer.Option(8000, help="HTTP port"),
        ) -> None:
            """Run the application as an HTTP API server (experimental)."""
            from tooli.api.server import serve_api

            serve_api(self, host=host, port=port)

        # Orchestration utilities
        orchestrate_app = typer.Typer(name="orchestrate", help="Programmatic orchestration", hidden=True)
        self.add_typer(orchestrate_app)

        @orchestrate_app.command(name="run", cls=TooliCommand)  # type: ignore[untyped-decorator]
        def orchestrate_run(
            plan_path: str | None = typer.Argument(
                None,
                help="Path to a JSON plan file. If omitted, reads from stdin.",
            ),
            python: bool = typer.Option(False, help="Evaluate stdin/plan input as a Python expression."),
            continue_on_error: bool = typer.Option(
                False,
                "--continue-on-error",
                help="Continue executing after a failed step.",
            ),
            max_steps: int = typer.Option(64, help="Maximum number of steps to execute."),
        ) -> dict[str, Any]:
            """Execute multiple Tooli commands from a structured plan."""
            import sys

            from tooli.errors import InputError
            from tooli.orchestration import parse_plan_payload, run_tool_plan

            if max_steps <= 0:
                raise InputError(message="max_steps must be greater than zero.", code="E1005")

            if plan_path in (None, "-"):
                raw_plan = sys.stdin.read()
            else:
                raw_plan = Path(str(plan_path)).read_text(encoding="utf-8")

            if not raw_plan.strip():
                return {"ok": False, "error": "No orchestration plan provided."}

            try:
                steps = parse_plan_payload(
                    raw_plan,
                    command_name="orchestrate",
                    allow_python=python,
                )
                return run_tool_plan(
                    self,
                    steps,
                    max_steps=max_steps,
                    continue_on_error=continue_on_error,
                )
            except ValueError as exc:
                raise InputError(message=str(exc), code="E1005") from exc

        @self.command(name="tooli_read_page", hidden=True, cls=TooliCommand)  # type: ignore[untyped-decorator]
        def tooli_read_page(path: str = typer.Argument(..., help="Path to an output artifact.")) -> None:
            """Read a text artifact written by token-aware truncation."""
            from tooli.errors import InputError

            artifact_root = Path(tempfile.gettempdir()) / "tooli_logs"
            artifact_path = Path(path)
            resolved = artifact_path.expanduser().resolve()

            if not str(resolved).startswith(str(artifact_root.resolve())):
                raise InputError(
                    message="tooli_read_page can only read files from the Tooli log directory.",
                    code="E1008",
                )

            if not resolved.exists():
                raise InputError(message="Artifact file not found.", code="E1009")

            if not resolved.is_file():
                raise InputError(message="Artifact path is not a file.", code="E1010")

            with open(resolved, encoding="utf-8") as handle:
                import click

                click.echo(handle.read())

        # Eval utilities
        eval_app = typer.Typer(name="eval", help="Evaluation tooling")
        self.add_typer(eval_app)

        @eval_app.command(name="analyze", cls=TooliCommand)
        def eval_analyze(log_path: str | None = None) -> dict[str, Any]:
            """Analyze invocation logs produced by Tooli(record=True) or TOOLI_RECORD."""
            from tooli.eval.analyzer import analyze_invocations

            default_path = os.getenv("TOOLI_RECORD")
            if self.invocation_recorder is not None:
                default_path = str(self.invocation_recorder.path)
            if log_path is None:
                log_path = default_path
            if isinstance(log_path, str) and not log_path.strip():
                log_path = None

            if log_path is None:
                return {
                    "error": "No log path provided. "
                    "Set TOOLI_RECORD, pass eval analyze <path>, or run Tooli(record=True)."
                }

            return analyze_invocations(log_path)

    def command(
        self,
        name: str | None = None,
        *,
        annotations: Any | None = None,
        list_processing: bool = False,
        paginated: bool = False,
        examples: list[dict[str, Any]] | None = None,
        error_codes: dict[str, str] | None = None,
        timeout: float | None = None,
        cost_hint: str | None = None,
        human_in_the_loop: bool = False,
        auth: list[str] | None = None,
        max_tokens: int | None = None,
        supports_dry_run: bool = False,
        requires_approval: bool = False,
        danger_level: str | None = None,
        allow_python_eval: bool = False,
        version: str | None = None,
        deprecated: bool = False,
        deprecated_message: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Register a command using Tooli defaults and metadata.

        By default, Tooli uses TooliCommand to inject global flags and route
        return values through the output system.
        """

        kwargs.setdefault("cls", TooliCommand)
        kwargs.setdefault("deprecated", deprecated)

        def _configure_callback(func: Any) -> None:
            # Preserve SecretInput markers for prompt/hidden-value redaction while
            # normalizing annotations for Typer argument parsing.
            secret_params: list[str] = []
            try:
                annotations_by_param = dict(get_type_hints(func, include_extras=True))
            except Exception:
                annotations_by_param = dict(func.__annotations__)
            for param_name, raw_annotation in annotations_by_param.items():
                if not is_secret_input(raw_annotation):
                    continue

                secret_params.append(param_name)
                annotation = raw_annotation

                # Unwrap Optional/Union wrappers to find the inner Annotated type.
                import types
                from typing import Union
                inner = annotation
                is_optional = False
                origin = get_origin(inner)
                if origin is Union or origin is getattr(types, "UnionType", None):
                    inner_args = [a for a in get_args(inner) if a is not type(None)]
                    is_optional = len(get_args(inner)) > len(inner_args)
                    if inner_args:
                        inner = inner_args[0]

                if get_origin(inner) is Annotated:
                    annotation_args = get_args(inner)
                    if annotation_args:
                        base_annotation = annotation_args[0]
                        metadata = annotation_args[1:]
                        if base_annotation is SecretInput:
                            resolved = str if not metadata else Annotated[(str, *metadata)]
                        else:
                            resolved = Annotated[(str, *metadata)] if metadata else str
                        annotation = Union[resolved, None] if is_optional else resolved  # type: ignore[assignment]  # noqa: UP007
                    else:
                        annotation = str
                else:
                    annotation = str

                annotations_by_param[param_name] = annotation

            func.__annotations__ = annotations_by_param

            meta = CommandMeta(
                app_name=self.info.name or "tooli",
                app_version=self.version,
                default_output=self.default_output,
                telemetry_pipeline=self.telemetry_pipeline,
                invocation_recorder=self.invocation_recorder,
                security_policy=self.security_policy,
                auth_context=self.auth_context,
                annotations=annotations,
                examples=examples or [],
                error_codes=error_codes or {},
                timeout=timeout,
                cost_hint=cost_hint,
                human_in_the_loop=human_in_the_loop,
                auth=auth or [],
                max_tokens=max_tokens,
                supports_dry_run=supports_dry_run,
                requires_approval=requires_approval,
                danger_level=danger_level,
                allow_python_eval=allow_python_eval,
                list_processing=bool(list_processing),
                paginated=bool(paginated),
                version=None if version is None else str(version),
                deprecated=deprecated,
                deprecated_message=deprecated_message,
                secret_params=secret_params,
            )
            func.__tooli_meta__ = meta

        if version is None:
            decorator = super().command(name=name, **kwargs)

            def _wrap(func: Any) -> Any:
                _configure_callback(func)
                return decorator(func)

            return _wrap

        def _wrap(func: Any) -> Any:  # type: ignore[no-redef]
            _configure_callback(func)
            base_name = name or func.__name__.replace("_", "-")
            is_hidden = bool(kwargs.get("hidden", False))
            version_suffix = version
            if version_suffix is None:
                version_suffix = "0.0.0"
            if not str(version_suffix).startswith("v"):
                versioned_alias = f"{base_name}-v{version_suffix}"
            else:
                versioned_alias = f"{base_name}-{version_suffix}"

            latest_kwargs = dict(kwargs)
            latest_kwargs.pop("hidden", None)
            latest_kwargs.pop("name", None)
            latest_kwargs["name"] = base_name
            latest_kwargs["deprecated"] = deprecated
            latest_kwargs["hidden"] = is_hidden
            latest_decorator = super(Tooli, self).command(**latest_kwargs)

            versioned_kwargs = dict(kwargs)
            versioned_kwargs.pop("name", None)
            versioned_kwargs["name"] = versioned_alias
            versioned_kwargs["hidden"] = True
            versioned_kwargs["deprecated"] = deprecated
            versioned_decorator = super(Tooli, self).command(**versioned_kwargs)

            versioned_decorator(func)

            latest_version = self._versioned_commands_latest.get(base_name)
            if latest_version is None or compare_versions(str(version), latest_version) >= 0:
                self._versioned_commands_latest[base_name] = str(version)
                for existing in self.registered_commands:
                    if existing.name == base_name:
                        existing.hidden = True
                return latest_decorator(func)

            return func

        return _wrap
