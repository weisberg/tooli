"""Tests for app.stream() and app.astream() (#166)."""

from __future__ import annotations

import pytest

from tooli import Tooli


def _make_app():
    app = Tooli(name="stream-app", version="1.0.0")

    @app.command()
    def list_items(n: int) -> list:
        """Return a list of items."""
        return [{"id": i, "name": f"item-{i}"} for i in range(n)]

    @app.command()
    def single_value(name: str) -> dict:
        """Return a single value."""
        return {"greeting": f"Hello, {name}!"}

    @app.command()
    def empty_list() -> list:
        """Return an empty list."""
        return []

    @app.command()
    def failing_command() -> str:
        """Command that raises."""
        from tooli.errors import InputError

        raise InputError("bad input", code="E1001")

    return app


class TestStream:
    def test_stream_list_yields_individual_items(self):
        app = _make_app()
        results = list(app.stream("list-items", n=3))
        assert len(results) == 3
        for i, r in enumerate(results):
            assert r.ok is True
            assert r.result["id"] == i
            assert r.result["name"] == f"item-{i}"

    def test_stream_single_value_yields_one_result(self):
        app = _make_app()
        results = list(app.stream("single-value", name="World"))
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].result["greeting"] == "Hello, World!"

    def test_stream_empty_list_yields_nothing(self):
        app = _make_app()
        results = list(app.stream("empty-list"))
        assert len(results) == 0

    def test_stream_error_yields_single_failure(self):
        app = _make_app()
        results = list(app.stream("failing-command"))
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].error is not None
        assert results[0].error.code == "E1001"

    def test_stream_unknown_command(self):
        app = _make_app()
        results = list(app.stream("nonexistent"))
        assert len(results) == 1
        assert results[0].ok is False

    def test_stream_meta_propagated(self):
        app = _make_app()
        results = list(app.stream("list-items", n=2))
        assert len(results) == 2
        for r in results:
            assert r.meta is not None
            assert "stream-app." in r.meta["tool"]

    def test_stream_can_iterate_lazily(self):
        """Verify stream works as a generator (lazy iteration)."""
        app = _make_app()
        gen = app.stream("list-items", n=5)
        first = next(gen)
        assert first.ok is True
        assert first.result["id"] == 0
        # Don't consume the rest — just verify lazy behavior


class TestAstream:
    @pytest.mark.asyncio
    async def test_astream_list_yields_individual_items(self):
        app = _make_app()
        results = []
        async for r in app.astream("list-items", n=3):
            results.append(r)
        assert len(results) == 3
        for i, r in enumerate(results):
            assert r.ok is True
            assert r.result["id"] == i

    @pytest.mark.asyncio
    async def test_astream_single_value(self):
        app = _make_app()
        results = []
        async for r in app.astream("single-value", name="Async"):
            results.append(r)
        assert len(results) == 1
        assert results[0].ok is True
        assert results[0].result["greeting"] == "Hello, Async!"

    @pytest.mark.asyncio
    async def test_astream_error(self):
        app = _make_app()
        results = []
        async for r in app.astream("failing-command"):
            results.append(r)
        assert len(results) == 1
        assert results[0].ok is False

    @pytest.mark.asyncio
    async def test_astream_empty_list(self):
        app = _make_app()
        results = []
        async for r in app.astream("empty-list"):
            results.append(r)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_astream_with_async_command(self):
        app = Tooli(name="async-stream-app", version="1.0.0")

        @app.command()
        async def async_list(n: int) -> list:
            """Async command returning a list."""
            return [{"i": i} for i in range(n)]

        results = []
        async for r in app.astream("async-list", n=2):
            results.append(r)
        assert len(results) == 2
        assert results[0].result["i"] == 0
        assert results[1].result["i"] == 1
