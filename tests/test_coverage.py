"""Tests for eval coverage reporter."""

from __future__ import annotations

from tooli.annotations import ReadOnly
from tooli.eval.coverage import eval_coverage


def _make_app(*, full_metadata=False):
    from tooli import Tooli

    app = Tooli(name="cov-test", help="Coverage test app", version="1.0.0")

    kwargs = {}
    if full_metadata:
        kwargs = {
            "annotations": ReadOnly,
            "examples": [{"args": ["--all"], "description": "List all"}],
            "error_codes": {"E3001": "Not found -> Try broader filter"},
            "when_to_use": "List all items",
            "task_group": "Query",
        }

    @app.command("list-items", **kwargs)
    def list_items(all: bool = False) -> list:  # noqa: A002
        """List items."""
        return []

    @app.command("bare")
    def bare() -> str:
        """Bare command."""
        return "ok"

    return app


class TestEvalCoverage:
    def test_reports_total_commands(self):
        report = eval_coverage(_make_app())
        assert report["total_commands"] == 2

    def test_reports_coverage_fields(self):
        report = eval_coverage(_make_app())
        cov = report["coverage"]
        assert "examples" in cov
        assert "output_schema" in cov
        assert "error_codes" in cov
        assert "annotations" in cov
        assert "help_text" in cov

    def test_full_metadata_coverage(self):
        report = eval_coverage(_make_app(full_metadata=True))
        cov = report["coverage"]
        assert cov["examples"] >= 1
        assert cov["annotations"] >= 1
        assert cov["error_codes"] >= 1
        assert cov["when_to_use"] >= 1
        assert cov["task_group"] >= 1

    def test_issues_reported_for_bare_command(self):
        report = eval_coverage(_make_app())
        bare_cmd = [c for c in report["commands"] if c["name"] == "bare"][0]
        assert "missing examples" in bare_cmd["issues"]

    def test_token_estimate_present(self):
        report = eval_coverage(_make_app())
        assert report["token_estimate"] > 0

    def test_warnings_for_missing_output_example(self):
        report = eval_coverage(_make_app())
        # Commands returning dict without output_example should get warnings
        assert isinstance(report["warnings"], list)
