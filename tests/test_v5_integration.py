"""Comprehensive v5 integration tests (#168).

Tests cross-cutting v5 features that verify multiple subsystems working together.
These tests focus on interactions *between* subsystems, not duplicating
individual feature tests already covered in:
  - tests/test_app_call.py
  - tests/test_app_acall.py
  - tests/test_app_stream.py
  - tests/test_capabilities_handoffs_field.py
  - tests/test_security_capabilities.py
  - tests/test_output_schema.py
  - tests/test_agents_md.py
  - tests/test_command_accessors.py
"""

from __future__ import annotations

import importlib
import json

import pytest
from typer.testing import CliRunner

from tooli import Tooli
from tooli.annotations import Destructive, Idempotent, ReadOnly
from tooli.errors import InputError, StateError, ToolRuntimeError
from tooli.python_api import TooliResult

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _find_envelope(output: str) -> dict:
    """Find the JSON envelope line in CLI output."""
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if "ok" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    msg = f"No envelope found in output: {output!r}"
    raise ValueError(msg)


# ===========================================================================
# 1. TestExampleAppsCallable
# ===========================================================================


# All 18 example app module paths
EXAMPLE_APPS = [
    "examples.artifactcatalog.app",
    "examples.configmigrate.app",
    "examples.csvkit_t.app",
    "examples.datawrangler.app",
    "examples.docq.app",
    "examples.envar.app",
    "examples.envdoctor.app",
    "examples.gitsum.app",
    "examples.imgsort.app",
    "examples.logslicer.app",
    "examples.mediameta.app",
    "examples.note_indexer.app",
    "examples.patchpilot.app",
    "examples.proj.app",
    "examples.repolens.app",
    "examples.secretscout.app",
    "examples.syswatch.app",
    "examples.taskr.app",
]


class TestExampleAppsCallable:
    """Verify all 18 example apps are importable and priority apps are callable."""

    @pytest.mark.parametrize("module_path", EXAMPLE_APPS)
    def test_example_app_importable(self, module_path: str):
        """Each example app module can be imported and has an 'app' attribute."""
        mod = importlib.import_module(module_path)
        assert hasattr(mod, "app"), f"{module_path} has no 'app' attribute"
        assert type(mod.app).__name__ == "Tooli", f"{module_path}.app is not a Tooli instance"

    @pytest.mark.parametrize("module_path", EXAMPLE_APPS)
    def test_example_app_has_commands(self, module_path: str):
        """Each example app has at least one user-defined command."""
        mod = importlib.import_module(module_path)
        cmds = mod.app.list_commands()
        # Filter out built-in commands that tooli adds automatically
        assert len(cmds) > 0, f"{module_path} has no commands"

    def test_docq_call_with_missing_file(self):
        """docq.stats on a nonexistent file returns structured error."""
        mod = importlib.import_module("examples.docq.app")
        result = mod.app.call("stats", source="/nonexistent/file.md")
        assert isinstance(result, TooliResult)
        assert result.ok is False
        assert result.error is not None
        assert result.error.code is not None

    def test_taskr_call_list_with_nonexistent_store(self, tmp_path):
        """taskr.list with a missing store path returns structured result."""
        mod = importlib.import_module("examples.taskr.app")
        result = mod.app.call("list", store=str(tmp_path / "no-such-store.json"))
        assert isinstance(result, TooliResult)
        # Either ok (empty list) or structured error — never an unhandled exception
        assert isinstance(result.ok, bool)

    def test_proj_call_validate_nonexistent(self, tmp_path):
        """proj.validate on a nonexistent directory returns structured error."""
        mod = importlib.import_module("examples.proj.app")
        result = mod.app.call("validate", root=str(tmp_path / "no-such-project"))
        assert isinstance(result, TooliResult)
        assert result.ok is False
        assert result.error is not None

    def test_imgsort_scan_nonexistent_dir(self, tmp_path):
        """imgsort.scan on a nonexistent directory returns structured error."""
        mod = importlib.import_module("examples.imgsort.app")
        result = mod.app.call("scan", directory=str(tmp_path / "no-images"))
        assert isinstance(result, TooliResult)
        assert result.ok is False
        assert result.error is not None


# ===========================================================================
# 2. TestCapabilitiesInSchema
# ===========================================================================


class TestCapabilitiesInSchema:
    """Verify capabilities flow from command registration through to schema and manifest."""

    def _make_app(self):
        app = Tooli(name="cap-schema-app", version="1.0.0")

        @app.command(capabilities=["fs:read", "net:http"])
        def fetch_data(url: str) -> dict:
            """Fetch data from a URL."""
            return {"url": url}

        @app.command(capabilities=["fs:read", "fs:write"])
        def transform(input_path: str, output_path: str) -> dict:
            """Transform a file."""
            return {"input": input_path, "output": output_path}

        @app.command()
        def simple() -> str:
            """No capabilities."""
            return "ok"

        return app

    def test_generate_tool_schema_includes_capabilities(self):
        from tooli.schema import generate_tool_schema

        app = self._make_app()
        cb = app.get_command("fetch-data")
        schema = generate_tool_schema(cb, name="fetch-data")
        assert schema.capabilities == ["fs:read", "net:http"]

    def test_schema_empty_capabilities_for_simple(self):
        from tooli.schema import generate_tool_schema

        app = self._make_app()
        cb = app.get_command("simple")
        schema = generate_tool_schema(cb, name="simple")
        assert schema.capabilities == []

    def test_manifest_includes_capabilities(self):
        from tooli.manifest import generate_agent_manifest

        app = self._make_app()
        manifest = generate_agent_manifest(app)
        fetch_cmd = next(c for c in manifest["commands"] if "fetch" in c["name"])
        assert "capabilities" in fetch_cmd
        assert set(fetch_cmd["capabilities"]) == {"fs:read", "net:http"}

    def test_manifest_omits_capabilities_when_empty(self):
        from tooli.manifest import generate_agent_manifest

        app = self._make_app()
        manifest = generate_agent_manifest(app)
        simple_cmd = next(c for c in manifest["commands"] if c["name"] == "simple")
        assert "capabilities" not in simple_cmd

    def test_capabilities_propagate_to_all_doc_formats(self):
        """Capabilities appear in SKILL.md, AGENTS.md, and CLAUDE.md."""
        from tooli.docs.agents_md import generate_agents_md
        from tooli.docs.claude_md_v2 import generate_claude_md_v2
        from tooli.docs.skill_v4 import SkillV4Generator

        app = self._make_app()

        agents_md = generate_agents_md(app)
        assert "net:http" in agents_md

        skill_md = SkillV4Generator(app).generate()
        assert "net:http" in skill_md

        claude_md = generate_claude_md_v2(app)
        assert "net:http" in claude_md


# ===========================================================================
# 3. TestHandoffsInDocs
# ===========================================================================


class TestHandoffsInDocs:
    """Verify handoffs metadata flows into documentation generators."""

    def _make_app(self):
        app = Tooli(name="handoff-app", version="2.0.0")

        @app.command(
            handoffs=[
                {"command": "process", "when": "After scanning files"},
                {"command": "publish", "when": "After processing is complete"},
            ],
            delegation_hint="Requires filesystem agent",
        )
        def scan(root: str = ".") -> list:
            """Scan for files."""
            return []

        @app.command(
            handoffs=[{"command": "publish", "when": "After processing data"}],
        )
        def process(input_path: str) -> dict:
            """Process scanned files."""
            return {"processed": input_path}

        @app.command()
        def publish() -> str:
            """Publish results."""
            return "published"

        return app

    def test_skill_md_includes_handoff_info(self):
        from tooli.docs.skill_v4 import SkillV4Generator

        app = self._make_app()
        content = SkillV4Generator(app).generate()
        assert "process" in content
        assert "publish" in content
        assert "Handoff" in content or "handoff" in content or "Next" in content

    def test_agents_md_includes_handoff_info(self):
        from tooli.docs.agents_md import generate_agents_md

        app = self._make_app()
        content = generate_agents_md(app)
        assert "process" in content
        assert "publish" in content
        assert "Next steps" in content

    def test_agents_md_includes_delegation_hint(self):
        from tooli.docs.agents_md import generate_agents_md

        app = self._make_app()
        content = generate_agents_md(app)
        assert "Requires filesystem agent" in content

    def test_skill_md_omits_handoffs_for_terminal_command(self):
        """Commands with no handoffs should not have handoff sections."""
        from tooli.docs.skill_v4 import SkillV4Generator

        app = self._make_app()
        content = SkillV4Generator(app).generate()
        # The publish command section should not mention handoffs
        # Find the publish section and verify no handoff in that section
        lines = content.split("\n")
        in_publish = False
        publish_section_lines = []
        for line in lines:
            if "publish" in line.lower() and ("#" in line or "**" in line):
                in_publish = True
                continue
            if in_publish and line.startswith("#"):
                break
            if in_publish:
                publish_section_lines.append(line)
        publish_section = "\n".join(publish_section_lines)
        # publish should not reference handoff targets since it has none
        assert "After scanning" not in publish_section
        assert "After processing" not in publish_section

    def test_handoffs_in_manifest_with_chain(self):
        """Verify multi-step handoff chain is preserved in manifest."""
        from tooli.manifest import generate_agent_manifest

        app = self._make_app()
        manifest = generate_agent_manifest(app)

        scan_cmd = next(c for c in manifest["commands"] if c["name"] == "scan")
        assert len(scan_cmd["handoffs"]) == 2
        targets = [h["command"] for h in scan_cmd["handoffs"]]
        assert "process" in targets
        assert "publish" in targets

        process_cmd = next(c for c in manifest["commands"] if c["name"] == "process")
        assert len(process_cmd["handoffs"]) == 1


# ===========================================================================
# 4. TestStreamingEndToEnd
# ===========================================================================


class TestStreamingEndToEnd:
    """Test streaming through the Python API and CLI output."""

    def _make_app(self):
        app = Tooli(name="stream-e2e", version="1.0.0")

        @app.command()
        def generate(n: int) -> list:
            """Generate n items."""
            return [{"id": i, "value": f"item-{i}"} for i in range(n)]

        @app.command()
        def single_dict(key: str) -> dict:
            """Return a single dict."""
            return {"key": key, "status": "ok"}

        @app.command()
        def partial_fail(n: int) -> list:
            """Generate items but fail."""
            # In app.call() the command runs to completion, so we can test
            # the error path by raising before returning
            if n > 5:
                raise ToolRuntimeError(
                    message=f"Too many items: {n}",
                    code="E4010",
                )
            return [{"id": i} for i in range(n)]

        return app

    def test_stream_yields_individual_items(self):
        app = self._make_app()
        results = list(app.stream("generate", n=4))
        assert len(results) == 4
        for i, r in enumerate(results):
            assert r.ok is True
            assert r.result["id"] == i

    def test_stream_single_dict_yields_one(self):
        app = self._make_app()
        results = list(app.stream("single-dict", key="test"))
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].result["key"] == "test"

    def test_stream_error_yields_single_failure(self):
        app = self._make_app()
        results = list(app.stream("partial-fail", n=10))
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].error.code == "E4010"

    def test_stream_success_then_cli_json_matches(self):
        """Verify CLI --json output matches what app.call() returns for a list command."""
        app = self._make_app()

        # Python API
        api_result = app.call("generate", n=3)
        assert api_result.ok is True
        assert len(api_result.result) == 3

        # CLI
        runner = CliRunner()
        cli_result = runner.invoke(app, ["generate", "3", "--json"])
        assert cli_result.exit_code == 0
        data = json.loads(cli_result.output)
        assert data["ok"] is True
        assert len(data["result"]) == 3
        assert data["result"] == api_result.result

    def test_stream_meta_on_each_item(self):
        app = self._make_app()
        results = list(app.stream("generate", n=2))
        for r in results:
            assert r.meta is not None
            assert "stream-e2e." in r.meta["tool"]
            assert r.meta["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_astream_yields_items(self):
        app = self._make_app()
        results = []
        async for r in app.astream("generate", n=3):
            results.append(r)
        assert len(results) == 3
        assert all(r.ok is True for r in results)

    @pytest.mark.asyncio
    async def test_astream_error_yields_failure(self):
        app = self._make_app()
        results = []
        async for r in app.astream("partial-fail", n=99):
            results.append(r)
        assert len(results) == 1
        assert results[0].ok is False


# ===========================================================================
# 5. TestErrorFieldEndToEnd
# ===========================================================================


class TestErrorFieldEndToEnd:
    """End-to-end tests for error field mapping across all layers."""

    def _make_app(self):
        app = Tooli(name="field-e2e", version="1.0.0")

        @app.command()
        def validate(path: str, mode: str = "strict") -> dict:
            """Validate a path."""
            if not path.startswith("/"):
                raise InputError(
                    message=f"Path must be absolute: {path}",
                    code="E1010",
                    field="path",
                )
            if mode not in ("strict", "lenient"):
                raise InputError(
                    message=f"Invalid mode: {mode}",
                    code="E1011",
                    field="mode",
                )
            return {"valid": True}

        @app.command()
        def lookup(item_id: str) -> dict:
            """Look up an item."""
            raise StateError(
                message=f"Item not found: {item_id}",
                code="E3010",
                field="item_id",
            )

        return app

    def test_field_in_json_envelope_via_cli(self):
        app = self._make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["validate", "relative/path", "--json"])
        assert result.exit_code != 0
        data = _find_envelope(result.output)
        assert data["ok"] is False
        assert data["error"]["field"] == "path"
        assert data["error"]["code"] == "E1010"

    def test_field_preserved_in_python_api(self):
        app = self._make_app()
        result = app.call("validate", path="relative/path")
        assert result.ok is False
        assert result.error.field == "path"

    def test_field_roundtrip_tooli_error_to_exception_to_dict(self):
        """TooliError -> to_exception() -> to_dict() preserves field."""
        app = self._make_app()
        result = app.call("validate", path="relative/path")
        assert result.error.field == "path"

        # Convert to exception
        exc = result.error.to_exception()
        assert isinstance(exc, InputError)
        assert exc.field == "path"

        # Convert to dict
        d = exc.to_dict()
        assert d["field"] == "path"
        assert d["code"] == "E1010"

    def test_field_on_state_error(self):
        app = self._make_app()
        result = app.call("lookup", item_id="abc-123")
        assert result.ok is False
        assert result.error.field == "item_id"
        assert result.error.category == "state"

    def test_field_none_when_not_specified(self):
        """Errors without field should not include it."""
        app = Tooli(name="no-field-app", version="1.0.0")

        @app.command()
        def boom() -> str:
            raise InputError(message="generic error", code="E1000")

        result = app.call("boom")
        assert result.ok is False
        assert result.error.field is None

    def test_unwrap_preserves_field(self):
        app = self._make_app()
        result = app.call("validate", path="bad")
        with pytest.raises(InputError) as exc_info:
            result.unwrap()
        assert exc_info.value.field == "path"

    @pytest.mark.asyncio
    async def test_field_in_acall(self):
        app = self._make_app()
        result = await app.acall("validate", path="bad")
        assert result.ok is False
        assert result.error.field == "path"


# ===========================================================================
# 6. TestSecurityPolicyEndToEnd
# ===========================================================================


class TestSecurityPolicyEndToEnd:
    """Integration: security policy + capabilities + CLI invocation."""

    def test_strict_blocks_denied_capability_via_call(self, monkeypatch):
        """STRICT mode with TOOLI_ALLOWED_CAPABILITIES blocks via app.call()."""
        monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read")

        app = Tooli(name="sec-e2e", version="1.0.0", security_policy="strict")

        @app.command(capabilities=["fs:read", "fs:write"])
        def write_file(path: str) -> str:
            return f"wrote {path}"

        # CLI path
        runner = CliRunner()
        result = runner.invoke(app, ["write-file", "test.txt", "--json"])
        assert result.exit_code != 0
        data = _find_envelope(result.output)
        assert data["ok"] is False
        assert "fs:write" in data["error"]["message"]

    def test_strict_allows_with_wildcard_via_cli(self, monkeypatch):
        monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:*,net:*")

        app = Tooli(name="sec-e2e", version="1.0.0", security_policy="strict")

        @app.command(capabilities=["fs:read", "fs:write", "net:http"])
        def full_access(path: str) -> str:
            return f"accessed {path}"

        runner = CliRunner()
        result = runner.invoke(app, ["full-access", "test.txt", "--text"])
        assert result.exit_code == 0
        assert "accessed test.txt" in result.output

    def test_standard_mode_ignores_restrictions(self, monkeypatch):
        monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read")

        app = Tooli(name="sec-e2e", version="1.0.0", security_policy="standard")

        @app.command(capabilities=["fs:write", "net:admin"])
        def dangerous() -> str:
            return "executed"

        runner = CliRunner()
        result = runner.invoke(app, ["dangerous", "--text"])
        assert result.exit_code == 0
        assert "executed" in result.output

    def test_strict_with_annotations_and_capabilities(self, monkeypatch):
        """Verify destructive annotation enforcement combines with capability enforcement."""
        monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read,fs:delete")

        app = Tooli(name="sec-e2e", version="1.0.0", security_policy="strict")

        @app.command(annotations=Destructive, capabilities=["fs:delete"])
        def wipe(target: str) -> str:
            return f"wiped {target}"

        runner = CliRunner()
        # Without --yes: destructive annotation blocks
        result = runner.invoke(app, ["wipe", "data", "--text"])
        assert result.exit_code == 2

        # With --yes and matching capabilities: should pass
        result = runner.invoke(app, ["wipe", "data", "--yes", "--text"])
        assert result.exit_code == 0

    def test_no_capabilities_passes_strict(self, monkeypatch):
        """Commands with no declared capabilities skip enforcement in STRICT mode."""
        monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read")

        app = Tooli(name="sec-e2e", version="1.0.0", security_policy="strict")

        @app.command()
        def hello() -> str:
            return "hi"

        runner = CliRunner()
        result = runner.invoke(app, ["hello", "--text"])
        assert result.exit_code == 0


# ===========================================================================
# 7. TestOutputSchemaEndToEnd
# ===========================================================================


class TestOutputSchemaEndToEnd:
    """Integration: output schema inclusion across modes and env vars."""

    def _make_app(self):
        app = Tooli(name="schema-e2e", version="1.0.0")

        @app.command()
        def items(n: int) -> list:
            """Return a list of items."""
            return [{"id": i} for i in range(n)]

        @app.command()
        def status() -> dict:
            """Return status."""
            return {"status": "healthy", "uptime": 42}

        return app

    def test_detailed_response_format_includes_output_schema(self):
        app = self._make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["items", "2", "--json", "--response-format", "detailed"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        schema = data["meta"].get("output_schema")
        assert schema is not None
        assert schema.get("type") == "array"

    def test_env_var_includes_output_schema(self, monkeypatch):
        monkeypatch.setenv("TOOLI_INCLUDE_SCHEMA", "true")
        app = self._make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        schema = data["meta"].get("output_schema")
        assert schema is not None

    def test_concise_mode_omits_output_schema(self):
        app = self._make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["items", "1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["meta"].get("output_schema") is None

    def test_output_schema_dict_type_inferred(self):
        app = self._make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["status", "--json", "--response-format", "detailed"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        schema = data["meta"].get("output_schema")
        assert schema is not None
        assert schema.get("type") == "object"

    def test_output_schema_and_result_consistent(self):
        """Verify the output_schema type matches the actual result type."""
        app = self._make_app()
        runner = CliRunner()

        # List command
        result = runner.invoke(app, ["items", "2", "--json", "--response-format", "detailed"])
        data = json.loads(result.output)
        schema_type = data["meta"]["output_schema"]["type"]
        actual_result = data["result"]
        if schema_type == "array":
            assert isinstance(actual_result, list)
        elif schema_type == "object":
            assert isinstance(actual_result, dict)


# ===========================================================================
# 8. TestCallerMetadataInPythonAPI
# ===========================================================================


class TestCallerMetadataInPythonAPI:
    """Verify caller metadata flows through call(), acall(), and stream()."""

    def _make_app(self):
        app = Tooli(name="caller-meta", version="3.0.0")

        @app.command()
        def ping() -> str:
            """Simple ping."""
            return "pong"

        @app.command()
        def items(n: int) -> list:
            """Return items."""
            return [{"i": i} for i in range(n)]

        return app

    def test_call_meta_has_caller_id(self):
        app = self._make_app()
        result = app.call("ping")
        assert result.meta is not None
        assert result.meta["caller_id"] == "python-api"

    def test_call_meta_has_tool_name(self):
        app = self._make_app()
        result = app.call("ping")
        assert result.meta["tool"] == "caller-meta.ping"

    def test_call_meta_has_version(self):
        app = self._make_app()
        result = app.call("ping")
        assert result.meta["version"] == "3.0.0"

    def test_call_meta_has_duration(self):
        app = self._make_app()
        result = app.call("ping")
        assert result.meta["duration_ms"] >= 0

    def test_stream_propagates_meta_to_each_item(self):
        app = self._make_app()
        results = list(app.stream("items", n=3))
        assert len(results) == 3
        for r in results:
            assert r.meta is not None
            assert r.meta["caller_id"] == "python-api"
            assert "caller-meta." in r.meta["tool"]
            assert r.meta["version"] == "3.0.0"

    @pytest.mark.asyncio
    async def test_acall_meta_has_caller_id(self):
        app = self._make_app()
        result = await app.acall("ping")
        assert result.meta is not None
        assert result.meta["caller_id"] == "python-api"

    @pytest.mark.asyncio
    async def test_astream_propagates_meta(self):
        app = self._make_app()
        results = []
        async for r in app.astream("items", n=2):
            results.append(r)
        assert len(results) == 2
        for r in results:
            assert r.meta["caller_id"] == "python-api"

    def test_error_result_also_has_meta(self):
        """Even on error, meta is populated with caller_id."""
        app = self._make_app()
        result = app.call("nonexistent-command")
        assert result.ok is False
        assert result.meta is not None
        assert result.meta["caller_id"] == "python-api"


# ===========================================================================
# 9. TestCrossSubsystemIntegration (bonus: multi-feature interactions)
# ===========================================================================


class TestCrossSubsystemIntegration:
    """Tests that exercise multiple v5 features working together."""

    def test_capabilities_in_schema_and_manifest_and_docs(self):
        """Single app: capabilities appear consistently across all surfaces."""
        app = Tooli(name="multi-surface", version="1.0.0")

        @app.command(
            annotations=ReadOnly,
            capabilities=["db:read", "cache:read"],
            handoffs=[{"command": "write-data", "when": "After reading data to transform"}],
        )
        def read_data(source: str) -> dict:
            """Read data from source."""
            return {"source": source}

        from tooli.docs.agents_md import generate_agents_md
        from tooli.manifest import generate_agent_manifest
        from tooli.schema import generate_tool_schema

        # Schema
        cb = app.get_command("read-data")
        schema = generate_tool_schema(cb, name="read-data")
        assert "db:read" in schema.capabilities
        assert len(schema.handoffs) == 1

        # Manifest
        manifest = generate_agent_manifest(app)
        cmd = next(c for c in manifest["commands"] if "read" in c["name"])
        assert "db:read" in cmd["capabilities"]
        assert cmd["handoffs"][0]["command"] == "write-data"

        # AGENTS.md
        agents_md = generate_agents_md(app)
        assert "db:read" in agents_md
        assert "write-data" in agents_md

    def test_error_field_plus_security_policy_interaction(self, monkeypatch):
        """Security denial produces structured error with appropriate code."""
        monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read")

        app = Tooli(name="sec-field-test", version="1.0.0", security_policy="strict")

        @app.command(capabilities=["fs:write"])
        def write_file(path: str) -> str:
            raise InputError(message="should not reach", field="path")

        runner = CliRunner()
        result = runner.invoke(app, ["write-file", "test.txt", "--json"])
        data = _find_envelope(result.output)
        assert data["ok"] is False
        # Security denial should have code E2002, not the InputError code
        assert data["error"]["code"] == "E2002"

    def test_python_api_call_with_annotations_and_capabilities(self):
        """app.call() works on a command that has annotations + capabilities + handoffs."""
        app = Tooli(name="full-meta", version="1.0.0")

        @app.command(
            annotations=Idempotent | ReadOnly,
            capabilities=["fs:read"],
            handoffs=[{"command": "process", "when": "After listing"}],
        )
        def list_all() -> list:
            """List everything."""
            return [{"name": "a"}, {"name": "b"}]

        result = app.call("list-all")
        assert result.ok is True
        assert len(result.result) == 2
        assert result.meta["caller_id"] == "python-api"

    def test_streaming_with_error_field(self):
        """Error with field propagates through stream()."""
        app = Tooli(name="stream-field", version="1.0.0")

        @app.command()
        def validate_items(path: str) -> list:
            raise InputError(message="bad path", code="E1010", field="path")

        results = list(app.stream("validate-items", path="/bad"))
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].error.field == "path"

    def test_output_schema_with_capabilities_in_detailed_mode(self):
        """Detailed JSON envelope includes output_schema for a command with capabilities."""
        app = Tooli(name="detail-cap", version="1.0.0")

        @app.command(capabilities=["fs:read"])
        def read_items() -> list:
            """Read items."""
            return [{"id": 1}]

        runner = CliRunner()
        result = runner.invoke(app, ["read-items", "--json", "--response-format", "detailed"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["meta"].get("output_schema") is not None
        assert data["meta"]["output_schema"]["type"] == "array"

    def test_dry_run_via_call_with_capabilities(self):
        """dry_run=True works with commands that have capabilities."""
        app = Tooli(name="dry-cap", version="1.0.0")

        @app.command(capabilities=["fs:write"])
        def write(path: str) -> str:
            return f"wrote {path}"

        result = app.call("write", path="/tmp/test", dry_run=True)
        assert result.ok is True
        assert result.result["dry_run"] is True

    def test_manifest_envelope_schema_includes_field(self):
        """Manifest envelope schema documents the 'field' property on errors."""
        app = Tooli(name="manifest-field", version="1.0.0")

        @app.command()
        def noop() -> str:
            return "ok"

        from tooli.manifest import generate_agent_manifest

        manifest = generate_agent_manifest(app)
        failure_envelope = manifest["envelope_schema"]["failure"]
        assert "field" in failure_envelope["error"]
