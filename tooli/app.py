"""Core Tooli application class extending Typer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Annotated, get_args, get_origin, get_type_hints
import os

import typer

from tooli.command import TooliCommand
from tooli.eval.recorder import build_invocation_recorder
from tooli.auth import AuthContext
from tooli.input import SecretInput, is_secret_input
from tooli.security.policy import resolve_security_policy
from tooli.telemetry_pipeline import build_telemetry_pipeline
from tooli.versioning import compare_versions


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
        # Register built-in commands
        self._register_builtins()

    def _register_builtins(self) -> None:
        @self.command(name="generate-skill", hidden=True)
        def generate_skill() -> None:
            """Generate SKILL.md for this application."""
            from tooli.docs.skill import generate_skill_md
            content = generate_skill_md(self)
            with open("SKILL.md", "w") as f:
                f.write(content)
            # Use click.echo as we are in a CLI context
            import click
            click.echo("Generated SKILL.md")

        # MCP group
        import typer
        mcp_app = typer.Typer(name="mcp", help="MCP server utilities", hidden=True)
        self.add_typer(mcp_app)

        @mcp_app.command(name="export")
        def mcp_export() -> None:
            """Export MCP tool definitions as JSON."""
            from tooli.mcp.export import export_mcp_tools
            import json
            import click
            tools = export_mcp_tools(self)
            click.echo(json.dumps(tools, indent=2))

        @mcp_app.command(name="serve")
        def mcp_serve(
            transport: str = typer.Option("stdio", help="MCP transport: stdio|http|sse"),
            host: str = typer.Option("localhost", help="HTTP/SSE host"),
            port: int = typer.Option(8080, help="HTTP/SSE port"),
        ) -> None:
            """Run the application as an MCP server."""
            from tooli.mcp.server import serve_mcp
            serve_mcp(self, transport=transport, host=host, port=port)

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
                if get_origin(annotation) is Annotated:
                    annotation_args = get_args(annotation)
                    if annotation_args:
                        base_annotation = annotation_args[0]
                        metadata = annotation_args[1:]
                        if base_annotation is SecretInput:
                            annotation = str if not metadata else Annotated[str, *metadata]
                        else:
                            annotation = Annotated[str, *metadata] if metadata else str
                else:
                    annotation = str

                annotations_by_param[param_name] = annotation

            setattr(func, "__annotations__", annotations_by_param)
            setattr(func, "__tooli_secret_params__", secret_params)

            # Attach app-level metadata to the callback for downstream use
            # (e.g., envelopes).
            setattr(func, "__tooli_app_name__", self.info.name or "tooli")
            setattr(func, "__tooli_app_version__", self.version)
            setattr(func, "__tooli_default_output__", self.default_output)

            # Attach command-level metadata
            setattr(func, "__tooli_annotations__", annotations)
            setattr(func, "__tooli_examples__", examples or [])
            setattr(func, "__tooli_error_codes__", error_codes or {})
            setattr(func, "__tooli_timeout__", timeout)
            setattr(func, "__tooli_cost_hint__", cost_hint)
            setattr(func, "__tooli_human_in_the_loop__", human_in_the_loop)
            setattr(func, "__tooli_auth__", auth or [])
            setattr(func, "__tooli_telemetry_pipeline__", self.telemetry_pipeline)
            setattr(func, "__tooli_invocation_recorder__", self.invocation_recorder)
            setattr(func, "__tooli_security_policy__", self.security_policy)
            setattr(func, "__tooli_auth_context__", self.auth_context)
            setattr(func, "__tooli_list_processing__", bool(list_processing))
            setattr(func, "__tooli_paginated__", bool(paginated))
            setattr(func, "__tooli_version__", None if version is None else str(version))
            setattr(func, "__tooli_deprecated__", deprecated)
            setattr(func, "__tooli_deprecated_message__", deprecated_message)

        if version is None:
            decorator = super().command(name=name, **kwargs)

            def _wrap(func: Any) -> Any:
                _configure_callback(func)
                return decorator(func)

            return _wrap

        def _wrap(func: Any) -> Any:
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
