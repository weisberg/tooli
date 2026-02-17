"""Tests for PipeContract storage, schema generation, and composition inference."""

from __future__ import annotations

from tooli.command_meta import get_command_meta
from tooli.manifest import generate_agent_manifest
from tooli.pipes import PipeContract, pipe_contracts_compatible


def _make_app():
    from tooli import Tooli

    return Tooli(name="pipe-test", help="Pipe test app", version="1.0.0")


class TestPipeContractStorage:
    def test_pipe_contract_round_trip(self):
        contract = PipeContract(
            format="jsonl",
            schema={"type": "object", "properties": {"id": {"type": "string"}}},
            description="Stream of objects",
            example='{"id": "1"}',
        )
        d = contract.to_dict()
        restored = PipeContract.from_dict(d)
        assert restored.format == "jsonl"
        assert restored.schema == contract.schema
        assert restored.description == "Stream of objects"
        assert restored.example == '{"id": "1"}'

    def test_minimal_contract(self):
        contract = PipeContract(format="csv")
        d = contract.to_dict()
        assert d == {"format": "csv"}
        restored = PipeContract.from_dict(d)
        assert restored.format == "csv"
        assert restored.schema is None
        assert restored.description == ""

    def test_stored_on_command_meta(self):
        app = _make_app()
        pipe_out = PipeContract(format="json", description="Items").to_dict()

        @app.command("emit", pipe_output=pipe_out)
        def emit() -> list:
            """Emit items."""
            return []

        meta = get_command_meta(emit)
        assert meta.pipe_output is not None
        assert meta.pipe_output["format"] == "json"


class TestPipeCompatibility:
    def test_same_format_compatible(self):
        a = PipeContract(format="json").to_dict()
        b = PipeContract(format="json").to_dict()
        assert pipe_contracts_compatible(a, b) is True

    def test_different_format_incompatible(self):
        a = PipeContract(format="json").to_dict()
        b = PipeContract(format="text").to_dict()
        assert pipe_contracts_compatible(a, b) is False

    def test_none_is_incompatible(self):
        a = PipeContract(format="json").to_dict()
        assert pipe_contracts_compatible(a, None) is False
        assert pipe_contracts_compatible(None, a) is False
        assert pipe_contracts_compatible(None, None) is False


class TestManifestPipeContracts:
    def test_pipe_contracts_in_manifest(self):
        app = _make_app()
        pipe_out = PipeContract(format="json").to_dict()
        pipe_in = PipeContract(format="json").to_dict()

        @app.command("source", pipe_output=pipe_out)
        def source() -> list:
            """Source."""
            return []

        @app.command("sink", pipe_input=pipe_in)
        def sink(data: str = "") -> str:
            """Sink."""
            return data

        manifest = generate_agent_manifest(app)
        commands = {c["name"]: c for c in manifest["commands"]}
        assert "pipe_output" in commands["source"]
        assert commands["source"]["pipe_output"]["format"] == "json"
        assert "pipe_input" in commands["sink"]
        assert commands["sink"]["pipe_input"]["format"] == "json"

    def test_no_pipe_contracts_omitted(self):
        app = _make_app()

        @app.command("plain")
        def plain() -> str:
            """No pipes."""
            return "ok"

        manifest = generate_agent_manifest(app)
        cmd = [c for c in manifest["commands"] if c["name"] == "plain"][0]
        assert "pipe_input" not in cmd
        assert "pipe_output" not in cmd


class TestCompositionInference:
    def test_skill_v4_infers_pipe_composition(self):
        from tooli.docs.skill_v4 import generate_skill_md

        app = _make_app()
        pipe_out = PipeContract(format="json").to_dict()
        pipe_in = PipeContract(format="json").to_dict()

        @app.command("source", pipe_output=pipe_out)
        def source() -> list:
            """Source data."""
            return []

        @app.command("sink", pipe_input=pipe_in)
        def sink(data: str = "") -> str:
            """Sink data."""
            return data

        content = generate_skill_md(app)
        assert "Pipe source into sink" in content
