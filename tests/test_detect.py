"""Tests for tooli.detect — cross-platform agent detection.

Exercises every detection pathway by monkeypatching environment variables,
process info, filesystem checks, and TTY status.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

import tooli.detect as mod
from tooli.detect import (
    CallerCategory,
    ExecutionContext,
    _check_call_stack,
    _check_ci,
    _check_container,
    _check_env_signatures,
    _check_process_tree,
    _format_json,
    _format_report,
    detect_execution_context,
    detected_agent_name,
    is_agent,
    is_automation,
    is_ci,
    reset_cache,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_cache():
    """Reset the module-level cache before and after each test."""
    reset_cache()
    yield
    reset_cache()


# ---------------------------------------------------------------------------
# 1. Environment variable fingerprints
# ---------------------------------------------------------------------------

class TestEnvSignatures:

    def test_claude_code_prefix(self):
        env = {"CLAUDE_CODE_ACTION": "run", "HOME": "/home/user"}
        hits = _check_env_signatures(env)
        names = [h[0] for h in hits]
        assert "Claude Code" in names
        assert any(h[2] == 1.0 for h in hits if h[0] == "Claude Code")

    def test_claude_code_simple(self):
        env = {"CLAUDE_CODE": "1"}
        hits = _check_env_signatures(env)
        names = [h[0] for h in hits]
        assert "Claude Code" in names

    def test_cursor(self):
        env = {"CURSOR_TRACE_ID": "abc123"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Cursor" for h in hits)

    def test_cursor_term_program(self):
        env = {"TERM_PROGRAM": "cursor"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Cursor" for h in hits)

    def test_codespaces(self):
        env = {"CODESPACES": "true"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "GitHub Codespaces" for h in hits)

    def test_github_copilot(self):
        env = {"GITHUB_COPILOT": "1"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "GitHub Copilot" for h in hits)

    def test_windsurf(self):
        env = {"WINDSURF_SESSION": "xyz"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Windsurf" for h in hits)

    def test_amazon_q(self):
        env = {"AMAZON_Q_SESSION": "1"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Amazon Q Developer" for h in hits)

    def test_aider(self):
        env = {"AIDER_MODEL": "gpt-4"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Aider" for h in hits)

    def test_devin(self):
        env = {"DEVIN_SESSION": "xyz"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Devin" for h in hits)

    def test_openai_codex(self):
        env = {"CODEX_CLI": "1"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "OpenAI Codex CLI" for h in hits)

    def test_langchain(self):
        env = {"LANGCHAIN_TRACING_V2": "true", "LANGCHAIN_API_KEY": "lsv2_..."}
        hits = _check_env_signatures(env)
        assert any(h[0] == "LangChain" for h in hits)

    def test_langsmith(self):
        env = {"LANGSMITH_API_KEY": "lsv2_..."}
        hits = _check_env_signatures(env)
        assert any(h[0] == "LangSmith" for h in hits)

    def test_continue_dev(self):
        env = {"CONTINUE_SESSION_ID": "abc"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Continue" for h in hits)

    def test_tooli_agent_mode(self):
        env = {"TOOLI_AGENT_MODE": "true"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Generic Agent" for h in hits)

    def test_empty_env(self):
        hits = _check_env_signatures({})
        assert hits == []


# ---------------------------------------------------------------------------
# 2. CI / CD detection
# ---------------------------------------------------------------------------

class TestCIDetection:

    @pytest.mark.parametrize("key,expected_name", [
        ("GITHUB_ACTIONS", "GitHub Actions"),
        ("GITLAB_CI", "GitLab CI"),
        ("JENKINS_URL", "Jenkins"),
        ("CIRCLECI", "CircleCI"),
        ("TRAVIS", "Travis CI"),
        ("BUILDKITE", "Buildkite"),
        ("TF_BUILD", "Azure Pipelines"),
        ("CODEBUILD_BUILD_ID", "AWS CodeBuild"),
        ("TEAMCITY_VERSION", "TeamCity"),
        ("BITBUCKET_PIPELINE_UUID", "Bitbucket Pipelines"),
        ("DRONE", "Drone CI"),
        ("VERCEL", "Vercel"),
        ("NETLIFY", "Netlify"),
    ])
    def test_specific_ci(self, key, expected_name):
        env = {key: "true"}
        hits = _check_ci(env)
        names = [h[0] for h in hits]
        assert expected_name in names

    def test_generic_ci_flag(self):
        env = {"CI": "true"}
        hits = _check_ci(env)
        assert any("CI" in h[0] for h in hits)

    def test_no_ci(self):
        env = {"HOME": "/home/user"}
        hits = _check_ci(env)
        assert hits == []


# ---------------------------------------------------------------------------
# 3. Container detection
# ---------------------------------------------------------------------------

class TestContainerDetection:

    def test_dockerenv(self):
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda p: p == "/.dockerenv"
            with patch("builtins.open", side_effect=FileNotFoundError):
                with patch("platform.system", return_value="Darwin"):
                    with patch("platform.machine", return_value="x86_64"):
                        hits = _check_container()
                        assert any(h[0] == "Docker" for h in hits)

    def test_wsl_detection(self):
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda p: p == "/proc/sys/fs/binfmt_misc/WSLInterop"
            with patch("builtins.open", side_effect=FileNotFoundError):
                with patch("platform.system", return_value="Linux"):
                    with patch("platform.release", return_value="5.15.0-1-microsoft-standard"):
                        with patch("platform.machine", return_value="x86_64"):
                            hits = _check_container()
                            assert any(h[0] == "WSL" for h in hits)

    def test_no_container(self):
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=FileNotFoundError):
                with patch("platform.system", return_value="Darwin"):
                    with patch("platform.machine", return_value="arm64"):
                        with patch("platform.release", return_value="23.4.0"):
                            hits = _check_container()
                            assert hits == []


# ---------------------------------------------------------------------------
# 4. Process tree
# ---------------------------------------------------------------------------

class TestProcessTree:

    def test_gh_parent(self):
        with patch.object(mod, "_get_parent_info", return_value=("gh", "gh copilot suggest")):
            with patch("platform.system", return_value="Darwin"):
                hits = _check_process_tree()
                assert any(h[0] == "GitHub Copilot CLI" for h in hits)

    def test_claude_binary_parent(self):
        with patch.object(mod, "_get_parent_info", return_value=("claude", "claude --help")):
            with patch("platform.system", return_value="Darwin"):
                hits = _check_process_tree()
                assert any(h[0] == "Claude Code" for h in hits)

    def test_node_running_claude(self):
        with patch.object(mod, "_get_parent_info",
                          return_value=("node", "node /usr/lib/claude-code/index.js")):
            with patch("platform.system", return_value="Linux"):
                hits = _check_process_tree()
                names = [h[0] for h in hits]
                assert "Claude Code" in names

    def test_node_wrapper_generic(self):
        with patch.object(mod, "_get_parent_info",
                          return_value=("node", "node /some/vscode/extension.js")):
            with patch("platform.system", return_value="Linux"):
                hits = _check_process_tree()
                names = [h[0] for h in hits]
                assert "Node.js wrapper" in names
                assert "Claude Code" not in names

    def test_python_wrapper(self):
        with patch.object(mod, "_get_parent_info",
                          return_value=("python3.12", "python3.12 agent_runner.py")):
            with patch("platform.system", return_value="Linux"):
                with patch.object(os.path, "basename", return_value="python3.11"):
                    hits = _check_process_tree()
                    assert any(h[0] == "Python wrapper" for h in hits)

    def test_human_shell_macos(self):
        with patch.object(mod, "_get_parent_info", return_value=("zsh", "-zsh")):
            with patch("platform.system", return_value="Darwin"):
                hits = _check_process_tree()
                assert any(h[0] == "Human Shell" and h[2] < 0 for h in hits)

    def test_human_shell_windows(self):
        with patch.object(mod, "_get_parent_info",
                          return_value=("powershell.exe", "powershell.exe")):
            with patch("platform.system", return_value="Windows"):
                hits = _check_process_tree()
                assert any(h[0] == "Human Shell" and h[2] < 0 for h in hits)

    def test_human_shell_linux(self):
        with patch.object(mod, "_get_parent_info", return_value=("bash", "/bin/bash")):
            with patch("platform.system", return_value="Linux"):
                hits = _check_process_tree()
                assert any(h[0] == "Human Shell" and h[2] < 0 for h in hits)

    def test_no_parent(self):
        with patch.object(mod, "_get_parent_info", return_value=None):
            hits = _check_process_tree()
            assert hits == []

    def test_no_false_positive_from_claude_in_path(self):
        """Regression: /home/claude in cmdline should NOT trigger Claude Code detection."""
        with patch.object(mod, "_get_parent_info",
                          return_value=("sh", "/bin/sh -c cd /home/claude && python script.py")):
            with patch("platform.system", return_value="Linux"):
                hits = _check_process_tree()
                names = [h[0] for h in hits]
                assert "Claude Code" not in names


# ---------------------------------------------------------------------------
# 5. Call stack inspection
# ---------------------------------------------------------------------------

class TestCallStack:

    def test_langchain_in_stack(self):
        fake_frame = MagicMock()
        fake_frame.frame.f_globals = {"__name__": "langchain.agents.runner"}
        with patch("inspect.stack", return_value=[fake_frame]):
            hits = _check_call_stack()
            assert any(h[0] == "LangChain" for h in hits)

    def test_crewai_in_stack(self):
        fake_frame = MagicMock()
        fake_frame.frame.f_globals = {"__name__": "crewai.task"}
        with patch("inspect.stack", return_value=[fake_frame]):
            hits = _check_call_stack()
            assert any(h[0] == "CrewAI" for h in hits)

    def test_autogen_in_stack(self):
        fake_frame = MagicMock()
        fake_frame.frame.f_globals = {"__name__": "autogen.agentchat"}
        with patch("inspect.stack", return_value=[fake_frame]):
            hits = _check_call_stack()
            assert any(h[0] == "AutoGen" for h in hits)

    def test_dspy_in_stack(self):
        fake_frame = MagicMock()
        fake_frame.frame.f_globals = {"__name__": "dspy.predict"}
        with patch("inspect.stack", return_value=[fake_frame]):
            hits = _check_call_stack()
            assert any(h[0] == "DSPy" for h in hits)

    def test_no_frameworks(self):
        fake_frame = MagicMock()
        fake_frame.frame.f_globals = {"__name__": "my_app.main"}
        with patch("inspect.stack", return_value=[fake_frame]):
            hits = _check_call_stack()
            assert hits == []


# ---------------------------------------------------------------------------
# 6. Full integration: detect_execution_context
# ---------------------------------------------------------------------------

class TestFullDetection:

    def test_claude_code_confirmed(self):
        """Claude Code env var → confirmed AI agent."""
        with patch.dict(os.environ, {"CLAUDE_CODE_ACTION": "run"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.AI_AGENT
                            assert ctx.agent_name == "Claude Code"
                            assert ctx.confidence >= 0.9

    def test_github_actions_ci(self):
        """GitHub Actions → CI/CD category."""
        with patch.dict(os.environ, {"CI": "true", "GITHUB_ACTIONS": "true"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.CI_CD
                            assert "GitHub Actions" in ctx.agent_name

    def test_human_interactive(self):
        """Interactive TTY with no agent signals → human."""
        with patch.dict(os.environ, {"TERM_PROGRAM": "iTerm.app", "SHELL": "/bin/zsh"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=True):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree",
                                      return_value=[("Human Shell", "Parent is zsh", -0.3)]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.HUMAN
                            assert ctx.is_interactive is True

    def test_langchain_inprocess(self):
        """LangChain env + call stack → AI agent."""
        with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack",
                                          return_value=[("LangChain", "Call stack includes langchain", 0.85)]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.AI_AGENT
                            assert ctx.agent_name == "LangChain"

    def test_container_only(self):
        """Docker container, non-interactive, no agent env → container."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container",
                                  return_value=[("Docker", "/.dockerenv exists", 0.95)]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.CONTAINER

    def test_non_interactive_unknown(self):
        """Piped input, no specific signals → unknown automation."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.UNKNOWN_AUTOMATION

    def test_cursor_with_tty(self):
        """Cursor env but with TTY (VS Code integrated terminal) → agent."""
        with patch.dict(os.environ, {"CURSOR_TRACE_ID": "abc", "TERM_PROGRAM": "cursor"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=True):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.AI_AGENT
                            assert ctx.agent_name == "Cursor"


# ---------------------------------------------------------------------------
# 7. Convenience helpers
# ---------------------------------------------------------------------------

class TestConvenienceHelpers:

    def test_is_agent(self):
        with patch.dict(os.environ, {"CLAUDE_CODE_ACTION": "1"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            assert is_agent() is True

    def test_is_ci(self):
        with patch.dict(os.environ, {"CI": "true", "GITHUB_ACTIONS": "true"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            assert is_ci() is True

    def test_is_automation(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            assert is_automation() is True

    def test_detected_agent_name_present(self):
        with patch.dict(os.environ, {"CLAUDE_CODE_ACTION": "1"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            assert detected_agent_name() == "Claude Code"

    def test_detected_agent_name_absent(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(mod, "_is_tty", return_value=True):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree",
                                      return_value=[("Human Shell", "Parent is zsh", -0.3)]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            assert detected_agent_name() is None


# ---------------------------------------------------------------------------
# 8. Output formatters
# ---------------------------------------------------------------------------

class TestFormatters:

    def test_format_report(self):
        ctx = ExecutionContext(
            category=CallerCategory.AI_AGENT,
            agent_name="Claude Code",
            confidence=1.0,
            signals=["CLAUDE_CODE_ACTION env var"],
            is_interactive=False,
            platform="Darwin",
        )
        report = _format_report(ctx)
        assert "Claude Code" in report
        assert "100%" in report
        assert "ai_agent" in report

    def test_format_json(self):
        import json
        ctx = ExecutionContext(
            category=CallerCategory.HUMAN,
            confidence=0.9,
            signals=[],
            is_interactive=True,
            platform="Windows",
        )
        data = json.loads(_format_json(ctx))
        assert data["category"] == "human"
        assert data["is_agent"] is False
        assert data["platform"] == "Windows"


# ---------------------------------------------------------------------------
# 9. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_multiple_agent_signals_boost_confidence(self):
        """When both env and process tree match, confidence should increase."""
        with patch.dict(os.environ, {"AIDER_MODEL": "gpt-4"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree",
                                      return_value=[("Aider", "Parent cmdline starts with 'aider'", 0.8)]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.agent_name == "Aider"
                            # Multi-signal should boost above single signal confidence
                            assert ctx.confidence > 0.9

    def test_ci_plus_agent_prefers_ci(self):
        """When CI env vars + weak agent signal, prefer CI classification."""
        with patch.dict(os.environ, {"CI": "true", "GITHUB_ACTIONS": "true"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree",
                                      return_value=[("Node.js wrapper", "Parent: node", 0.5)]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.CI_CD

    def test_cache_reuse(self):
        """Calling convenience helpers twice uses cached result."""
        with patch.dict(os.environ, {"CLAUDE_CODE_ACTION": "1"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            name1 = detected_agent_name()
                            name2 = detected_agent_name()
                            assert name1 == name2 == "Claude Code"


# ---------------------------------------------------------------------------
# 10. TOOLI_CALLER Convention
# ---------------------------------------------------------------------------

class TestTooliCallerConvention:
    """Tests for the TOOLI_CALLER / TOOLI_CALLER_VERSION / TOOLI_SESSION_ID
    convention — the recommended, highest-confidence identification method."""

    def test_tooli_caller_known_agent(self):
        """Well-known TOOLI_CALLER value maps to display name."""
        with patch.dict(os.environ, {"TOOLI_CALLER": "claude-code"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                ctx = detect_execution_context()
                assert ctx.category == CallerCategory.AI_AGENT
                assert ctx.agent_name == "Claude Code"
                assert ctx.confidence == 1.0
                assert ctx.caller_id == "claude-code"
                assert ctx.identified_via_convention is True

    def test_tooli_caller_custom_agent(self):
        """Unknown TOOLI_CALLER value is used as-is for agent_name."""
        with patch.dict(os.environ, {"TOOLI_CALLER": "my-org-build-bot"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                ctx = detect_execution_context()
                assert ctx.category == CallerCategory.AI_AGENT
                assert ctx.agent_name == "my-org-build-bot"
                assert ctx.caller_id == "my-org-build-bot"
                assert ctx.confidence == 1.0

    def test_tooli_caller_with_version(self):
        """TOOLI_CALLER_VERSION is captured in the result."""
        env = {"TOOLI_CALLER": "aider", "TOOLI_CALLER_VERSION": "0.82.1"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                ctx = detect_execution_context()
                assert ctx.agent_name == "Aider"
                assert ctx.caller_version == "0.82.1"

    def test_tooli_caller_with_session_id(self):
        """TOOLI_SESSION_ID is captured in the result."""
        env = {"TOOLI_CALLER": "crewai", "TOOLI_SESSION_ID": "run-abc-123"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                ctx = detect_execution_context()
                assert ctx.agent_name == "CrewAI"
                assert ctx.session_id == "run-abc-123"

    def test_tooli_caller_all_fields(self):
        """All three TOOLI_* fields populated together."""
        env = {
            "TOOLI_CALLER": "cursor",
            "TOOLI_CALLER_VERSION": "2.1.0",
            "TOOLI_SESSION_ID": "sess_xyz789",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(mod, "_is_tty", return_value=True):
                ctx = detect_execution_context()
                assert ctx.agent_name == "Cursor"
                assert ctx.caller_id == "cursor"
                assert ctx.caller_version == "2.1.0"
                assert ctx.session_id == "sess_xyz789"
                assert ctx.confidence == 1.0
                assert ctx.is_interactive is True  # TTY preserved

    def test_tooli_caller_case_insensitive(self):
        """TOOLI_CALLER is lowercased for matching."""
        with patch.dict(os.environ, {"TOOLI_CALLER": "Claude-Code"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                ctx = detect_execution_context()
                assert ctx.agent_name == "Claude Code"
                assert ctx.caller_id == "claude-code"

    def test_tooli_caller_stripped(self):
        """Whitespace is stripped from TOOLI_CALLER."""
        with patch.dict(os.environ, {"TOOLI_CALLER": "  devin  "}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                ctx = detect_execution_context()
                assert ctx.agent_name == "Devin"
                assert ctx.caller_id == "devin"

    def test_tooli_caller_skips_heuristics(self):
        """When TOOLI_CALLER is set, heuristic checks are NOT called."""
        env = {"TOOLI_CALLER": "langchain", "GITHUB_ACTIONS": "true"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_ci") as mock_ci:
                    with patch.object(mod, "_check_container") as mock_container:
                        with patch.object(mod, "_check_process_tree") as mock_proc:
                            with patch.object(mod, "_check_call_stack") as mock_stack:
                                ctx = detect_execution_context()
                                # None of the heuristic functions should have been called
                                mock_ci.assert_not_called()
                                mock_container.assert_not_called()
                                mock_proc.assert_not_called()
                                mock_stack.assert_not_called()
                                # But still correctly identified
                                assert ctx.agent_name == "LangChain"
                                assert ctx.confidence == 1.0

    def test_tooli_caller_empty_is_ignored(self):
        """Empty TOOLI_CALLER falls through to heuristic detection."""
        with patch.dict(os.environ, {"TOOLI_CALLER": ""}, clear=True):
            with patch.object(mod, "_is_tty", return_value=True):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree",
                                      return_value=[("Human Shell", "Parent is bash", -0.3)]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.HUMAN
                            assert ctx.caller_id is None

    def test_tooli_caller_whitespace_only_is_ignored(self):
        """Whitespace-only TOOLI_CALLER falls through to heuristic detection."""
        with patch.dict(os.environ, {"TOOLI_CALLER": "   "}, clear=True):
            with patch.object(mod, "_is_tty", return_value=True):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree",
                                      return_value=[("Human Shell", "Parent is zsh", -0.3)]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.category == CallerCategory.HUMAN

    def test_tooli_caller_signal_description(self):
        """Signal description includes version and truncated session."""
        env = {
            "TOOLI_CALLER": "windsurf",
            "TOOLI_CALLER_VERSION": "3.0.0",
            "TOOLI_SESSION_ID": "a-very-long-session-id-that-gets-truncated",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                ctx = detect_execution_context()
                signal = ctx.signals[0]
                assert "TOOLI_CALLER=windsurf" in signal
                assert "v3.0.0" in signal
                assert "session=a-very-long-sess" in signal  # truncated to 16 chars

    def test_tooli_caller_overrides_other_env_signals(self):
        """TOOLI_CALLER takes precedence even when other agent env vars present."""
        env = {
            "TOOLI_CALLER": "custom-orchestrator",
            "CLAUDE_CODE_ACTION": "run",
            "LANGCHAIN_TRACING_V2": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                ctx = detect_execution_context()
                assert ctx.agent_name == "custom-orchestrator"
                assert ctx.caller_id == "custom-orchestrator"

    def test_heuristic_fallback_has_no_caller_id(self):
        """When detected via heuristics, caller_id/version/session are None."""
        with patch.dict(os.environ, {"CLAUDE_CODE_ACTION": "run"}, clear=True):
            with patch.object(mod, "_is_tty", return_value=False):
                with patch.object(mod, "_check_container", return_value=[]):
                    with patch.object(mod, "_check_process_tree", return_value=[]):
                        with patch.object(mod, "_check_call_stack", return_value=[]):
                            ctx = detect_execution_context()
                            assert ctx.agent_name == "Claude Code"
                            assert ctx.caller_id is None
                            assert ctx.caller_version is None
                            assert ctx.session_id is None
                            assert ctx.identified_via_convention is False

    def test_env_signatures_returns_early_for_tooli_caller(self):
        """_check_env_signatures returns a single hit and stops for TOOLI_CALLER."""
        env = {
            "TOOLI_CALLER": "aider",
            "TOOLI_CALLER_VERSION": "0.82.1",
            "CLAUDE_CODE_ACTION": "run",  # would normally also match
        }
        hits = _check_env_signatures(env)
        assert len(hits) == 1
        assert hits[0][0] == "Aider"
        assert hits[0][2] == 1.0

    def test_legacy_tooli_agent_mode_still_works(self):
        """TOOLI_AGENT_MODE=true still triggers without TOOLI_CALLER."""
        env = {"TOOLI_AGENT_MODE": "true"}
        hits = _check_env_signatures(env)
        assert any(h[0] == "Generic Agent" for h in hits)

    def test_all_well_known_caller_ids_have_display_names(self):
        """Every well-known caller ID in the lookup table resolves."""
        for caller_id, display in mod._TOOLI_CALLER_DISPLAY_NAMES.items():
            env = {"TOOLI_CALLER": caller_id}
            hits = _check_env_signatures(env)
            assert len(hits) == 1
            assert hits[0][0] == display
            assert hits[0][2] == 1.0
