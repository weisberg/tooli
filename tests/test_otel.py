"""Tests for optional OpenTelemetry command spans."""

from __future__ import annotations

import types

from typer.testing import CliRunner

from tooli import Tooli


def _install_fake_opentelemetry(state: dict[str, object]) -> None:
    """Register a fake opentelemetry.trace module that records span attributes."""

    class FakeStatusCode:
        ERROR = "ERROR"

    class FakeStatus:
        def __init__(self, code: object, description: str) -> None:
            self.code = code
            self.description = description

    class FakeSpan:
        def __init__(self) -> None:
            self.attributes: dict[str, object] = {}
            self.status: object | None = None
            self.ended = False

        def set_attribute(self, key: str, value: object) -> None:
            self.attributes[key] = value

        def set_status(self, status: object) -> None:
            self.status = status

        def end(self) -> None:
            self.ended = True

    class FakeTracer:
        def start_span(self, name: str) -> FakeSpan:
            state["span_name"] = name
            state["span"] = FakeSpan()
            return state["span"]

    class FakeTraceModule(types.SimpleNamespace):
        def __init__(self) -> None:
            super().__init__(
                get_tracer=lambda _name: FakeTracer(),
                Status=FakeStatus,
                StatusCode=FakeStatusCode,
            )

    fake_trace_module = FakeTraceModule()
    fake_opentelemetry_module = types.SimpleNamespace(trace=fake_trace_module)

    import sys

    sys.modules["opentelemetry"] = fake_opentelemetry_module
    sys.modules["opentelemetry.trace"] = fake_trace_module


def test_otel_span_records_command_attributes_when_enabled(monkeypatch) -> None:
    state: dict[str, object] = {}
    _install_fake_opentelemetry(state)
    monkeypatch.setenv("TOOLI_OTEL_ENABLED", "1")

    app = Tooli(name="otel-app")

    @app.command()
    def greet(name: str) -> str:
        return f"hello {name}"

    result = CliRunner().invoke(app, ["greet", "Alice", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "hello Alice"

    span = state.get("span")
    assert span is not None
    assert span.attributes["tooli.command"] == "otel-app.greet"
    assert span.attributes["tooli.exit_code"] == 0
    assert span.attributes["tooli.error_category"] == "none"
    assert span.attributes["tooli.arguments"] == "{\"name\":\"Alice\"}"
    assert span.ended is True


def test_otel_disabled_path_never_imports_trace(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_OTEL_ENABLED", "0")

    monkeypatch.setattr(
        "tooli.telemetry._load_opentelemetry_trace",
        lambda: (_ for _ in ()).throw(AssertionError("OTel import attempted while disabled")),
    )

    app = Tooli(name="otel-app")

    @app.command()
    def ping() -> str:
        return "pong"

    result = CliRunner().invoke(app, ["ping", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "pong"
