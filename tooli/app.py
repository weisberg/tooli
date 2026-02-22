"""Core Tooli application class extending Typer."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable  # noqa: TC003
from pathlib import Path  # noqa: TC003
from typing import Annotated, Any, get_args, get_origin, get_type_hints

import click  # noqa: TC002
import typer
from typer.main import TyperGroup  # type: ignore[attr-defined]

from tooli.auth import AuthContext
from tooli.backends.native import translate_marker
from tooli.command import TooliCommand, _emit_parser_error, _is_agent_mode
from tooli.command_meta import CommandMeta, PromptMeta, ResourceMeta, get_command_meta
from tooli.recorder import build_invocation_recorder
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
    is Tooli-native -- Typer is an implementation detail.
    """

    def __init__(
        self,
        *args: Any,
        backend: str = "typer",
        description: str | None = None,
        triggers: list[str] | None = None,
        anti_triggers: list[str] | None = None,
        workflows: list[dict[str, Any]] | None = None,
        rules: list[str] | None = None,
        env_vars: dict[str, Any] | None = None,
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
        if backend not in {"typer", "native"}:
            raise ValueError("backend must be 'typer' or 'native'")
        backend_requested = backend
        if backend == "native":
            # Native backend is currently scaffolded but currently routes through
            # Typer-compatible command metadata handling for compatibility.
            backend = "typer"
        kwargs.setdefault("cls", TooliGroup)
        if description is not None and kwargs.get("help") is None:
            kwargs["help"] = description

        super().__init__(*args, **kwargs)

        # Tooli-specific configuration
        self.version = version
        self.default_output = default_output
        self.mcp_transport = mcp_transport
        self.skill_auto_generate = skill_auto_generate
        self.triggers = list(triggers or [])
        self.anti_triggers = list(anti_triggers or [])
        self.workflows = list(workflows or [])
        self.rules = list(rules or [])
        self.env_vars = env_vars or {}
        self.backend = backend_requested
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

    def call(self, command_name: str, **kwargs: Any) -> Any:
        """Invoke a command by name as a Python function call.

        Bypasses CLI parsing but uses the same validation, error handling,
        telemetry, and recording pipeline.  Returns a ``TooliResult``.

        Parameters
        ----------
        command_name:
            Command name (hyphens or underscores accepted).
        **kwargs:
            Arguments to pass to the command function.

        Returns
        -------
        TooliResult
            Structured result with ``ok``, ``result``, ``error``, and ``meta``.
        """
        import inspect
        import time

        from tooli.errors import InternalError, ToolError
        from tooli.python_api import TooliError, TooliResult

        app_name = self.info.name or "tooli"
        start = time.perf_counter()

        # Resolve command by name (accept hyphens or underscores)
        normalized = command_name.replace("_", "-")
        callback = None
        resolved_name = normalized
        for tool_def in self.get_tools():
            tool_name_normalized = tool_def.name.replace("_", "-")
            if tool_name_normalized == normalized or tool_def.name == command_name:
                callback = tool_def.callback
                resolved_name = tool_def.name
                break

        tool_id = f"{app_name}.{resolved_name}"

        def _build_meta(duration_ms: int) -> dict[str, Any]:
            return {
                "tool": tool_id,
                "version": self.version,
                "duration_ms": duration_ms,
                "caller_id": "python-api",
            }

        if callback is None:
            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            err = TooliError(
                code="E1001",
                category="input",
                message=f"Unknown command: {command_name}",
            )
            return TooliResult(ok=False, error=err, meta=_build_meta(duration_ms))

        # Extract special kwargs that map to framework flags
        dry_run = kwargs.pop("dry_run", False)

        # Validate kwargs against the function signature
        sig = inspect.signature(callback)
        valid_params = set()
        for param in sig.parameters.values():
            if param.name in ("ctx", "context"):
                continue
            if param.kind in {inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL}:
                continue
            valid_params.add(param.name)

        unknown = set(kwargs.keys()) - valid_params
        if unknown:
            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            from tooli.errors import InputError
            err_exc = InputError(
                message=f"Unknown parameter(s): {', '.join(sorted(unknown))}",
                code="E1001",
            )
            return TooliResult.from_tool_error(err_exc, meta=_build_meta(duration_ms))

        # Telemetry
        from tooli.telemetry import duration_ms as otel_duration_ms
        from tooli.telemetry import start_command_span

        command_span = start_command_span(command=tool_id, arguments=kwargs)
        command_span.set_caller(
            caller_id="python-api",
            caller_version=None,
            session_id=None,
        )

        # Execute
        try:
            if dry_run:
                result = {
                    "dry_run": True,
                    "command": resolved_name,
                    "arguments": kwargs,
                }
            else:
                result = callback(**kwargs)

            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            meta = _build_meta(duration_ms)

            # Record invocation
            if self.invocation_recorder is not None:
                self.invocation_recorder.record(
                    command=tool_id,
                    args=kwargs,
                    status="success",
                    duration_ms=duration_ms,
                    caller_id="python-api",
                )

            # Telemetry
            command_span.set_outcome(
                exit_code=0,
                error_category=None,
                duration_ms=otel_duration_ms(start),
            )
            if self.telemetry_pipeline is not None:
                self.telemetry_pipeline.record(
                    command=tool_id,
                    success=True,
                    duration_ms=duration_ms,
                    exit_code=0,
                )

            return TooliResult(ok=True, result=result, meta=meta)

        except ToolError as e:
            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            meta = _build_meta(duration_ms)

            if self.invocation_recorder is not None:
                self.invocation_recorder.record(
                    command=tool_id,
                    args=kwargs,
                    status="error",
                    duration_ms=duration_ms,
                    error_code=e.code,
                    caller_id="python-api",
                )

            command_span.set_outcome(
                exit_code=1,
                error_category=e.category.value,
                duration_ms=otel_duration_ms(start),
            )
            if self.telemetry_pipeline is not None:
                self.telemetry_pipeline.record(
                    command=tool_id,
                    success=False,
                    duration_ms=duration_ms,
                    exit_code=1,
                    error_code=e.code,
                    error_category=e.category.value,
                )

            return TooliResult.from_tool_error(e, meta=meta)

        except Exception as e:
            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            meta = _build_meta(duration_ms)
            internal_err = InternalError(message=f"Internal error: {e}")

            if self.invocation_recorder is not None:
                self.invocation_recorder.record(
                    command=tool_id,
                    args=kwargs,
                    status="error",
                    duration_ms=duration_ms,
                    error_code=internal_err.code,
                    caller_id="python-api",
                )

            command_span.set_outcome(
                exit_code=1,
                error_category="internal",
                duration_ms=otel_duration_ms(start),
            )

            return TooliResult.from_tool_error(internal_err, meta=meta)

    async def acall(self, command_name: str, **kwargs: Any) -> Any:
        """Async variant of ``call()``.

        If the command function is a coroutine, it is awaited directly.
        Otherwise the synchronous function is run via ``asyncio.to_thread()``.

        Returns a ``TooliResult`` -- same type and semantics as ``call()``.
        """
        import asyncio
        import inspect as _inspect


        # Resolve the callback to check if it's async
        normalized = command_name.replace("_", "-")
        callback = None
        for tool_def in self.get_tools():
            tool_name_normalized = tool_def.name.replace("_", "-")
            if tool_name_normalized == normalized or tool_def.name == command_name:
                callback = tool_def.callback
                break

        if callback is not None and _inspect.iscoroutinefunction(callback):
            # Async command -- call() internals but with await
            return await self._acall_async(command_name, callback, **kwargs)

        # Sync command -- delegate to call() in a thread
        return await asyncio.to_thread(self.call, command_name, **kwargs)

    async def _acall_async(self, command_name: str, callback: Any, **kwargs: Any) -> Any:
        """Execute an async command callback directly."""
        import inspect
        import time

        from tooli.errors import InternalError, ToolError
        from tooli.python_api import TooliResult

        app_name = self.info.name or "tooli"
        start = time.perf_counter()

        normalized = command_name.replace("_", "-")
        resolved_name = normalized
        for tool_def in self.get_tools():
            tool_name_normalized = tool_def.name.replace("_", "-")
            if tool_name_normalized == normalized or tool_def.name == command_name:
                resolved_name = tool_def.name
                break

        tool_id = f"{app_name}.{resolved_name}"

        def _build_meta(duration_ms: int) -> dict[str, Any]:
            return {
                "tool": tool_id,
                "version": self.version,
                "duration_ms": duration_ms,
                "caller_id": "python-api",
            }

        dry_run = kwargs.pop("dry_run", False)

        sig = inspect.signature(callback)
        valid_params = set()
        for param in sig.parameters.values():
            if param.name in ("ctx", "context"):
                continue
            if param.kind in {inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL}:
                continue
            valid_params.add(param.name)

        unknown = set(kwargs.keys()) - valid_params
        if unknown:
            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            from tooli.errors import InputError
            err_exc = InputError(
                message=f"Unknown parameter(s): {', '.join(sorted(unknown))}",
                code="E1001",
            )
            return TooliResult.from_tool_error(err_exc, meta=_build_meta(duration_ms))

        from tooli.telemetry import duration_ms as otel_duration_ms
        from tooli.telemetry import start_command_span

        command_span = start_command_span(command=tool_id, arguments=kwargs)
        command_span.set_caller(caller_id="python-api", caller_version=None, session_id=None)

        try:
            if dry_run:
                result = {"dry_run": True, "command": resolved_name, "arguments": kwargs}
            else:
                result = await callback(**kwargs)

            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            meta = _build_meta(duration_ms)

            if self.invocation_recorder is not None:
                self.invocation_recorder.record(
                    command=tool_id, args=kwargs, status="success",
                    duration_ms=duration_ms, caller_id="python-api",
                )

            command_span.set_outcome(exit_code=0, error_category=None, duration_ms=otel_duration_ms(start))
            if self.telemetry_pipeline is not None:
                self.telemetry_pipeline.record(
                    command=tool_id, success=True, duration_ms=duration_ms, exit_code=0,
                )

            return TooliResult(ok=True, result=result, meta=meta)

        except ToolError as e:
            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            meta = _build_meta(duration_ms)

            if self.invocation_recorder is not None:
                self.invocation_recorder.record(
                    command=tool_id, args=kwargs, status="error",
                    duration_ms=duration_ms, error_code=e.code, caller_id="python-api",
                )

            command_span.set_outcome(exit_code=1, error_category=e.category.value, duration_ms=otel_duration_ms(start))
            return TooliResult.from_tool_error(e, meta=meta)

        except Exception as e:
            duration_ms = max(1, int((time.perf_counter() - start) * 1000))
            meta = _build_meta(duration_ms)
            internal_err = InternalError(message=f"Internal error: {e}")

            if self.invocation_recorder is not None:
                self.invocation_recorder.record(
                    command=tool_id, args=kwargs, status="error",
                    duration_ms=duration_ms, error_code=internal_err.code, caller_id="python-api",
                )

            command_span.set_outcome(exit_code=1, error_category="internal", duration_ms=otel_duration_ms(start))
            return TooliResult.from_tool_error(internal_err, meta=meta)

    def stream(self, command_name: str, **kwargs: Any) -> Any:
        """Invoke a command and yield individual ``TooliResult`` items.

        For commands that return a list, each element is yielded as a
        separate ``TooliResult(ok=True, result=item)``.  Non-list results
        are yielded as a single ``TooliResult``.  Errors are yielded as
        a single ``TooliResult(ok=False, ...)``.

        Returns an ``Iterator[TooliResult]``.
        """
        from tooli.python_api import TooliResult

        result = self.call(command_name, **kwargs)
        if not result.ok:
            yield result
            return

        if isinstance(result.result, list):
            for item in result.result:
                yield TooliResult(ok=True, result=item, meta=result.meta)
        else:
            yield result

    async def astream(self, command_name: str, **kwargs: Any) -> Any:
        """Async variant of ``stream()``.

        Yields individual ``TooliResult`` items asynchronously.
        """
        from tooli.python_api import TooliResult

        result = await self.acall(command_name, **kwargs)
        if not result.ok:
            yield result
            return

        if isinstance(result.result, list):
            for item in result.result:
                yield TooliResult(ok=True, result=item, meta=result.meta)
        else:
            yield result

    def list_commands(self, ctx: click.Context | None = None) -> list[str]:
        """Override click help output to use transformed command names."""
        del ctx
        return sorted(tool.name for tool in self.get_tools() if not tool.hidden)

    def get_command(self, command_name: str) -> Callable[..., Any] | None:
        """Look up a command callback by name.

        Returns the callable or ``None`` if not found.  Accepts both
        hyphenated (``find-files``) and underscored (``find_files``) names.
        """
        normalized = command_name.replace("_", "-")
        for tool_def in self.get_tools():
            tool_name_normalized = tool_def.name.replace("_", "-")
            if tool_name_normalized == normalized or tool_def.name == command_name:
                return tool_def.callback
        return None

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
        @self.command(name="detect-context", cls=TooliCommand, hidden=True)  # type: ignore[untyped-decorator]
        def detect_context() -> dict[str, Any] | str:
            """Detect the current execution context (human, agent, CI, container)."""
            from tooli.detect import (
                _format_json,
                detect_execution_context,
            )

            ctx = detect_execution_context()
            import json
            return json.loads(_format_json(ctx))

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
        output_example: Any | None = None,
        version: str | None = None,
        deprecated: bool = False,
        deprecated_message: str | None = None,
        deprecated_version: str | None = None,
        when_to_use: str | None = None,
        expected_outputs: list[dict[str, Any]] | None = None,
        task_group: str | None = None,
        capabilities: list[str] | None = None,
        handoffs: list[dict[str, str]] | None = None,
        delegation_hint: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Register a command using Tooli defaults and metadata.

        By default, Tooli uses TooliCommand to inject global flags and route
        return values through the output system.
        """

        kwargs.setdefault("cls", TooliCommand)
        kwargs.setdefault("deprecated", deprecated)

        def _normalize_backend_metadata(annotation: Any) -> Any:
            if get_origin(annotation) is not Annotated:
                return annotation

            args = get_args(annotation)
            if len(args) <= 1:
                return annotation

            base_annotation = args[0]
            translated = [base_annotation]
            for marker in args[1:]:
                translated.append(translate_marker(marker))

            return Annotated[tuple(translated)] if len(translated) != 2 else Annotated[base_annotation, translated[1]]

        def _configure_callback(func: Any) -> None:
            # Preserve SecretInput markers for prompt/hidden-value redaction while
            # normalizing annotations for Typer argument parsing.
            secret_params: list[str] = []
            try:
                annotations_by_param = dict(get_type_hints(func, include_extras=True))
            except Exception:
                annotations_by_param = dict(func.__annotations__)
            for param_name, raw_annotation in annotations_by_param.items():
                annotations_by_param[param_name] = _normalize_backend_metadata(raw_annotation)
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
                app=self,
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
                output_example=output_example,
                list_processing=bool(list_processing),
                paginated=bool(paginated),
                version=None if version is None else str(version),
                deprecated=deprecated,
                deprecated_message=deprecated_message,
                deprecated_version=deprecated_version,
                secret_params=secret_params,
                when_to_use=when_to_use,
                expected_outputs=expected_outputs or [],
                task_group=task_group,
                capabilities=capabilities or [],
                handoffs=handoffs or [],
                delegation_hint=delegation_hint,
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
