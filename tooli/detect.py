"""Cross-platform agent and execution context detection for Tooli.

Determines whether a tooli CLI is being invoked by a human user, a specific
AI agent (Claude Code, GitHub Copilot, Cursor, etc.), an agent framework
(LangChain, AutoGen, CrewAI), a CI/CD pipeline, or some other automated
context.  Detection uses a triangulation strategy across five signal
categories:

    1. Environment variables  – agents and CI systems inject known keys.
    2. Process tree inspection – humans run shells; agents run node/python/docker.
    3. TTY / interactive status – humans have a TTY; pipes and agents do not.
    4. Container / sandbox markers – dockerenv, cgroup, WSL interop files.
    5. In-process call-stack inspection – detects LangChain / LangGraph callers.

The module is intentionally dependency-light: ``psutil`` is used when
available for richer process-tree data, but every code path has a stdlib
fallback so the module works in constrained environments (containers,
minimal Docker images, CI runners).

Tooli Caller Convention
-----------------------
Agents that are aware of tooli should set the ``TOOLI_CALLER`` environment
variable before invoking any tooli-built CLI.  This is the **recommended,
highest-confidence** identification method and takes priority over all
heuristic detection.

    TOOLI_CALLER          – Agent identifier string (e.g. "claude-code",
                            "copilot-workspace", "my-custom-agent").
    TOOLI_CALLER_VERSION  – Optional semver of the calling agent.
    TOOLI_SESSION_ID      – Optional opaque session/run ID for tracing.
    TOOLI_AGENT_MODE      – Legacy boolean flag (1/true/yes/on).  Still
                            honored but ``TOOLI_CALLER`` is preferred.

When ``TOOLI_CALLER`` is set, the detection module returns immediately with
confidence 1.0 — no heuristic probing is performed.

Public API
----------
detect_execution_context()  -> ExecutionContext   # full structured result
is_agent()                  -> bool               # quick predicate
detected_agent_name()       -> str | None         # e.g. "Claude Code"
"""

from __future__ import annotations

import inspect
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Tooli Caller Convention — environment variable names
# ---------------------------------------------------------------------------
# Agents SHOULD set these before invoking any tooli-built CLI.
# See AGENT_INTEGRATION.md for full guidance.

TOOLI_CALLER: str = "TOOLI_CALLER"
"""Primary self-identification variable.  Value is a short, lowercase,
hyphen-separated identifier for the calling agent or framework.

Well-known values:
    claude-code, cursor, copilot-workspace, copilot-cli, aider, devin,
    windsurf, amazon-q, codex-cli, continue, langchain, autogen, crewai,
    llamaindex, haystack, semantic-kernel, pydantic-ai, dspy, smolagents,
    agency-swarm, openai-agents-sdk, custom

Agents that do not match a well-known value should use a descriptive slug
(e.g. ``"my-org-build-bot"``).
"""

TOOLI_CALLER_VERSION: str = "TOOLI_CALLER_VERSION"
"""Optional semver string for the calling agent (e.g. ``"1.4.2"``)."""

TOOLI_SESSION_ID: str = "TOOLI_SESSION_ID"
"""Optional opaque identifier for the current session or run.  Useful for
correlating multiple CLI invocations that belong to the same agent task."""

TOOLI_AGENT_MODE: str = "TOOLI_AGENT_MODE"
"""Legacy boolean flag (``1``, ``true``, ``yes``, ``on``).  Still honored
for backward compatibility but ``TOOLI_CALLER`` is preferred."""

# Mapping from TOOLI_CALLER well-known values → display names
_TOOLI_CALLER_DISPLAY_NAMES: dict[str, str] = {
    "claude-code": "Claude Code",
    "cursor": "Cursor",
    "copilot-workspace": "GitHub Copilot Workspace",
    "copilot-cli": "GitHub Copilot CLI",
    "aider": "Aider",
    "devin": "Devin",
    "windsurf": "Windsurf",
    "amazon-q": "Amazon Q Developer",
    "codex-cli": "OpenAI Codex CLI",
    "continue": "Continue",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "autogen": "AutoGen",
    "crewai": "CrewAI",
    "llamaindex": "LlamaIndex",
    "haystack": "Haystack",
    "semantic-kernel": "Semantic Kernel",
    "pydantic-ai": "PydanticAI",
    "dspy": "DSPy",
    "smolagents": "SmolAgents",
    "agency-swarm": "Agency Swarm",
    "openai-agents-sdk": "OpenAI Agents SDK",
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class CallerCategory(str, Enum):
    """Top-level classification of who is running this process."""

    HUMAN = "human"
    AI_AGENT = "ai_agent"
    CI_CD = "ci_cd"
    CONTAINER = "container"
    UNKNOWN_AUTOMATION = "unknown_automation"


@dataclass(frozen=True)
class ExecutionContext:
    """Structured detection result returned by :func:`detect_execution_context`."""

    category: CallerCategory
    """Primary classification."""

    agent_name: str | None = None
    """Specific agent name when identified (e.g. ``"Claude Code"``)."""

    confidence: float = 0.0
    """0.0–1.0 confidence in the classification."""

    signals: list[str] = field(default_factory=list)
    """Human-readable list of every signal that fired."""

    is_interactive: bool = False
    """True when stdin/stdout are connected to a TTY."""

    platform: str = field(default_factory=platform.system)
    """Operating system: ``Darwin``, ``Linux``, ``Windows``."""

    caller_id: str | None = None
    """Raw TOOLI_CALLER value when set (e.g. ``"claude-code"``)."""

    caller_version: str | None = None
    """TOOLI_CALLER_VERSION value when set (e.g. ``"1.4.2"``)."""

    session_id: str | None = None
    """TOOLI_SESSION_ID value when set."""

    @property
    def is_agent(self) -> bool:
        return self.category == CallerCategory.AI_AGENT

    @property
    def is_ci(self) -> bool:
        return self.category == CallerCategory.CI_CD

    @property
    def is_human(self) -> bool:
        return self.category == CallerCategory.HUMAN

    @property
    def identified_via_convention(self) -> bool:
        """True when the caller used the TOOLI_CALLER convention."""
        return self.caller_id is not None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _env() -> dict[str, str]:
    """Snapshot of environment (mockable in tests)."""
    return dict(os.environ)


def _getenv(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _is_tty() -> bool:
    """Return True when both stdin and stdout look interactive."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 1. Environment-variable fingerprints
# ---------------------------------------------------------------------------

def _check_env_signatures(env: dict[str, str]) -> list[tuple[str, str, float]]:
    """Return ``(agent_name, signal_description, confidence)`` tuples.

    Ordered from most-specific to least-specific so the first match at
    confidence >= 0.9 can be treated as confirmed.
    """
    hits: list[tuple[str, str, float]] = []

    # ── TOOLI_CALLER convention (highest priority) ─────────────────────
    # When an agent explicitly self-identifies via the tooli convention,
    # this is a definitive signal — confidence 1.0, no guessing needed.
    tooli_caller = env.get(TOOLI_CALLER, "").strip().lower()
    if tooli_caller:
        display = _TOOLI_CALLER_DISPLAY_NAMES.get(tooli_caller, tooli_caller)
        version_str = env.get(TOOLI_CALLER_VERSION, "")
        session_str = env.get(TOOLI_SESSION_ID, "")
        desc_parts = [f"TOOLI_CALLER={tooli_caller}"]
        if version_str:
            desc_parts.append(f"v{version_str}")
        if session_str:
            desc_parts.append(f"session={session_str[:16]}")
        hits.append((display, " ".join(desc_parts), 1.0))
        # Return immediately — convention-based ID is authoritative
        return hits

    # ── TOOLI_AGENT_MODE (legacy boolean) ──────────────────────────────
    if env.get(TOOLI_AGENT_MODE, "").lower() in {"1", "true", "yes", "on"}:
        hits.append(("Generic Agent", "TOOLI_AGENT_MODE explicitly set", 0.85))

    # ── Claude Code ────────────────────────────────────────────────────
    if any(k.startswith("CLAUDE_CODE_") for k in env):
        hits.append(("Claude Code", "CLAUDE_CODE_* env var present", 1.0))
    elif env.get("CLAUDE_CODE"):
        hits.append(("Claude Code", "CLAUDE_CODE env var present", 0.95))

    # ── Cursor / AI IDE ────────────────────────────────────────────────
    if env.get("CURSOR_TRACE_ID") or env.get("CURSOR_SESSION_ID"):
        hits.append(("Cursor", "CURSOR_* env var present", 0.95))
    # Cursor's terminal sets TERM_PROGRAM=cursor
    if env.get("TERM_PROGRAM", "").lower() == "cursor":
        hits.append(("Cursor", "TERM_PROGRAM=cursor", 0.7))

    # ── Windsurf (Codeium) ─────────────────────────────────────────────
    if any(k.startswith("WINDSURF_") for k in env):
        hits.append(("Windsurf", "WINDSURF_* env var present", 0.95))

    # ── GitHub Copilot ecosystem ───────────────────────────────────────
    if env.get("CODESPACES", "").lower() == "true":
        hits.append(("GitHub Codespaces", "CODESPACES=true", 0.95))
    if env.get("GITHUB_COPILOT") or env.get("COPILOT_AGENT"):
        hits.append(("GitHub Copilot", "GITHUB_COPILOT / COPILOT_AGENT env var", 0.9))

    # ── Amazon CodeWhisperer / Q Developer ─────────────────────────────
    if any(k.startswith("CODEWHISPERER_") or k.startswith("AMAZON_Q_") for k in env):
        hits.append(("Amazon Q Developer", "CODEWHISPERER_/AMAZON_Q_* env var", 0.9))

    # ── Aider ──────────────────────────────────────────────────────────
    if env.get("AIDER_MODEL") or any(k.startswith("AIDER_") for k in env):
        hits.append(("Aider", "AIDER_* env var present", 0.9))

    # ── Continue.dev ───────────────────────────────────────────────────
    if any(k.startswith("CONTINUE_") for k in env):
        hits.append(("Continue", "CONTINUE_* env var present", 0.85))

    # ── Devin ──────────────────────────────────────────────────────────
    if env.get("DEVIN_SESSION") or any(k.startswith("DEVIN_") for k in env):
        hits.append(("Devin", "DEVIN_* env var present", 0.95))

    # ── OpenAI Codex CLI ───────────────────────────────────────────────
    if env.get("OPENAI_CODEX") or any(k.startswith("CODEX_") for k in env):
        hits.append(("OpenAI Codex CLI", "OPENAI_CODEX / CODEX_* env var", 0.9))

    # ── LangChain / LangSmith ──────────────────────────────────────────
    if "LANGCHAIN_TRACING_V2" in env or "LANGCHAIN_API_KEY" in env:
        hits.append(("LangChain", "LANGCHAIN env vars present", 0.8))
    if "LANGSMITH_API_KEY" in env:
        hits.append(("LangSmith", "LANGSMITH_API_KEY present", 0.7))

    return hits


# ---------------------------------------------------------------------------
# 2. CI / CD environment detection
# ---------------------------------------------------------------------------

_CI_SIGNATURES: list[tuple[str, str]] = [
    # (env-var key, descriptive CI name)
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
    ("WOODPECKER_CI", "Woodpecker CI"),
    ("RENDER", "Render"),
    ("VERCEL", "Vercel"),
    ("NETLIFY", "Netlify"),
    ("HEROKU_APP_NAME", "Heroku"),
    ("RAILWAY_ENVIRONMENT", "Railway"),
    ("FLY_APP_NAME", "Fly.io"),
]


def _check_ci(env: dict[str, str]) -> list[tuple[str, str, float]]:
    """Detect CI/CD runners.  Returns ``(ci_name, signal, confidence)``."""
    hits: list[tuple[str, str, float]] = []

    # Generic CI flag (many systems set this)
    if env.get("CI", "").lower() in {"true", "1", "yes"}:
        hits.append(("CI (generic)", "CI=true", 0.85))

    for key, name in _CI_SIGNATURES:
        if key in env:
            hits.append((name, f"{key} env var present", 0.95))

    return hits


# ---------------------------------------------------------------------------
# 3. Container / sandbox detection (cross-platform)
# ---------------------------------------------------------------------------

def _check_container() -> list[tuple[str, str, float]]:
    """Detect containerized / sandboxed execution environments."""
    hits: list[tuple[str, str, float]] = []
    system = platform.system()

    # ── Docker ─────────────────────────────────────────────────────────
    if os.path.exists("/.dockerenv"):
        hits.append(("Docker", "/.dockerenv exists", 0.95))

    # cgroup-based detection (Linux / containers on any host OS)
    if system == "Linux":
        try:
            with open("/proc/1/cgroup") as f:
                cgroup = f.read()
            if "docker" in cgroup or "containerd" in cgroup:
                hits.append(("Docker", "/proc/1/cgroup references docker/containerd", 0.9))
            if "kubepods" in cgroup:
                hits.append(("Kubernetes", "/proc/1/cgroup references kubepods", 0.9))
            if "lxc" in cgroup:
                hits.append(("LXC", "/proc/1/cgroup references lxc", 0.85))
        except (FileNotFoundError, PermissionError):
            pass

        # Overlay filesystem marker
        try:
            with open("/proc/1/mountinfo") as f:
                mounts = f.read()
            if "overlay" in mounts.split("\n")[0]:
                hits.append(("Container (overlay fs)", "PID 1 on overlay filesystem", 0.7))
        except (FileNotFoundError, PermissionError, IndexError):
            pass

    # ── WSL (Windows Subsystem for Linux) ──────────────────────────────
    if system == "Linux":
        if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop") or "microsoft" in platform.release().lower():
            hits.append(("WSL", "WSL interop markers detected", 0.9))

    # ── Windows containers ─────────────────────────────────────────────
    if system == "Windows":
        # Windows containers set a well-known env var
        if os.environ.get("CONTAINER", "").lower() == "true":
            hits.append(("Windows Container", "CONTAINER=true on Windows", 0.85))
        # Hyper-V isolation leaves a marker
        if os.path.exists(r"C:\ServiceProfiles"):
            # Heuristic: combined with other signals
            pass

    # ── macOS sandbox / containerized Linux on Apple Silicon ───────────
    if system == "Linux" and platform.machine() in ("arm64", "aarch64"):
        # Linux on ARM is common for containers built on Apple Silicon Macs
        hits.append(("Possible macOS Docker", "Linux arm64 (may be Apple Silicon container)", 0.5))

    return hits


# ---------------------------------------------------------------------------
# 4. Process tree inspection (cross-platform, psutil-optional)
# ---------------------------------------------------------------------------

def _get_parent_info_psutil() -> tuple[str, str] | None:
    """Use psutil to get parent process name and cmdline."""
    try:
        import psutil  # type: ignore[import-untyped]
        proc = psutil.Process(os.getpid())
        parent = proc.parent()
        if parent is None:
            return None
        name = parent.name().lower()
        cmdline = " ".join(parent.cmdline()).lower()
        return (name, cmdline)
    except Exception:
        return None


def _get_parent_info_fallback() -> tuple[str, str] | None:
    """Stdlib fallback for parent process info."""
    system = platform.system()
    ppid = os.getppid()
    if ppid <= 0:
        return None

    try:
        if system == "Windows":
            # Use WMIC or tasklist; PowerShell is too slow for a quick check
            result = subprocess.run(
                ["wmic", "process", "where", f"ProcessId={ppid}",
                 "get", "Name,CommandLine", "/format:list"],
                capture_output=True, text=True, timeout=3,
            )
            lines = result.stdout.strip().splitlines()
            name = ""
            cmdline = ""
            for line in lines:
                if line.startswith("CommandLine="):
                    cmdline = line.split("=", 1)[1].lower()
                elif line.startswith("Name="):
                    name = line.split("=", 1)[1].lower()
            if name:
                return (name, cmdline)
        else:
            # POSIX: use /proc or ps
            proc_comm = f"/proc/{ppid}/comm"
            proc_cmdline = f"/proc/{ppid}/cmdline"
            if os.path.exists(proc_comm):
                with open(proc_comm) as f:
                    name = f.read().strip().lower()
                cmdline = ""
                if os.path.exists(proc_cmdline):
                    with open(proc_cmdline) as f:
                        cmdline = f.read().replace("\0", " ").strip().lower()
                return (name, cmdline)
            else:
                # macOS and BSDs: fall back to ps
                result = subprocess.run(
                    ["ps", "-p", str(ppid), "-o", "comm=,args="],
                    capture_output=True, text=True, timeout=3,
                )
                if result.returncode == 0 and result.stdout.strip():
                    parts = result.stdout.strip().split(None, 1)
                    name = parts[0].lower() if parts else ""
                    cmdline = parts[1].lower() if len(parts) > 1 else name
                    return (name, cmdline)
    except Exception:
        pass

    return None


def _get_parent_info() -> tuple[str, str] | None:
    """Get (parent_name, parent_cmdline) using best available method."""
    info = _get_parent_info_psutil()
    if info is not None:
        return info
    return _get_parent_info_fallback()


def _check_process_tree() -> list[tuple[str, str, float]]:
    """Inspect parent process for agent / automation signatures."""
    hits: list[tuple[str, str, float]] = []
    info = _get_parent_info()
    if info is None:
        return hits

    name, cmdline = info

    # ── Specific agent runtimes ────────────────────────────────────────
    if name == "gh" or "copilot-agent" in cmdline:
        hits.append(("GitHub Copilot CLI", f"Parent process: {name}", 0.85))

    # Claude Code: look for the actual Claude Code binary or node process
    # running Claude Code, not just any path containing "claude"
    if name in ("claude", "claude-code"):
        hits.append(("Claude Code", f"Parent process: {name}", 0.85))
    elif "node" in name and ("claude" in cmdline.split("node", 1)[-1]):
        # Node process with Claude in the script path (not working dir)
        hits.append(("Claude Code", "Parent is Node.js running Claude Code", 0.8))

    if "cursor" in name:
        hits.append(("Cursor", f"Parent process: {name}", 0.75))

    if "aider" in cmdline.split(None, 1)[0] if cmdline else "":
        hits.append(("Aider", "Parent cmdline starts with 'aider'", 0.8))

    if name in ("devin", "devin-agent") or "devin-agent" in cmdline:
        hits.append(("Devin", f"Parent process: {name}", 0.8))

    # ── Generic wrapper runtimes ───────────────────────────────────────
    if "node" in name or "electron" in name:
        hits.append(("Node.js wrapper", f"Parent process: {name} (typical of VS Code extensions, Claude Code)", 0.5))

    if "python" in name and name != os.path.basename(sys.executable).lower():
        # A *different* Python is our parent — likely an agent runner
        hits.append(("Python wrapper", f"Parent process: {name} (likely agent runner)", 0.4))

    # ── Human-indicative shells (reduce agent confidence) ──────────────
    system = platform.system()
    human_shells: set[str] = set()
    if system == "Darwin":
        human_shells = {"zsh", "bash", "fish", "tcsh", "login"}
    elif system == "Linux":
        human_shells = {"bash", "zsh", "fish", "sh", "dash", "ksh", "tcsh", "login"}
    elif system == "Windows":
        human_shells = {"cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal"}

    if any(shell in name for shell in human_shells):
        hits.append(("Human Shell", f"Parent is human shell: {name}", -0.3))

    # ── Terminal emulators (strong human signal) ───────────────────────
    terminal_programs: set[str] = set()
    if system == "Darwin":
        terminal_programs = {"iterm2", "terminal", "alacritty", "kitty", "warp", "hyper"}
    elif system == "Linux":
        terminal_programs = {
            "gnome-terminal", "konsole", "xfce4-terminal", "alacritty",
            "kitty", "tilix", "terminator", "xterm", "urxvt", "warp",
            "foot", "st",
        }
    elif system == "Windows":
        terminal_programs = {"windowsterminal", "conhost.exe", "mintty"}

    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if term_program and any(tp in term_program for tp in terminal_programs):
        hits.append(("Terminal Emulator", f"TERM_PROGRAM={term_program}", -0.3))

    return hits


# ---------------------------------------------------------------------------
# 5. In-process call-stack inspection
# ---------------------------------------------------------------------------

_FRAMEWORK_MODULE_PREFIXES: list[tuple[str, str]] = [
    ("langchain", "LangChain"),
    ("langgraph", "LangGraph"),
    ("autogen", "AutoGen"),
    ("crewai", "CrewAI"),
    ("llama_index", "LlamaIndex"),
    ("haystack", "Haystack"),
    ("semantic_kernel", "Semantic Kernel"),
    ("marvin", "Marvin"),
    ("pydantic_ai", "PydanticAI"),
    ("dspy", "DSPy"),
    ("agency_swarm", "Agency Swarm"),
    ("smolagents", "SmolAgents"),
    ("openai.agents", "OpenAI Agents SDK"),
]


def _check_call_stack() -> list[tuple[str, str, float]]:
    """Inspect the Python call stack for agent framework callers."""
    hits: list[tuple[str, str, float]] = []
    seen: set[str] = set()

    try:
        for frame_info in inspect.stack():
            mod_name = frame_info.frame.f_globals.get("__name__", "")
            for prefix, framework_name in _FRAMEWORK_MODULE_PREFIXES:
                if prefix in mod_name and framework_name not in seen:
                    seen.add(framework_name)
                    hits.append((
                        framework_name,
                        f"Call stack includes {prefix} module",
                        0.85,
                    ))
    except Exception:
        # inspect.stack() can fail in some embedded environments
        pass

    return hits


# ---------------------------------------------------------------------------
# Assembler: combine all signals into a final verdict
# ---------------------------------------------------------------------------

def detect_execution_context() -> ExecutionContext:
    """Run all detection heuristics and return a structured verdict.

    This is the primary public entry point.  It is designed to be called
    once at process startup and the result cached for the lifetime of
    the CLI invocation.

    When ``TOOLI_CALLER`` is set in the environment, the function returns
    immediately with confidence 1.0 — no heuristic probing is performed.

    Returns
    -------
    ExecutionContext
        A frozen dataclass with ``category``, ``agent_name``,
        ``confidence``, ``signals``, ``is_interactive``, ``platform``,
        ``caller_id``, ``caller_version``, and ``session_id``.
    """
    env = _env()
    is_interactive = _is_tty()
    system = platform.system()

    # Extract TOOLI_* convention values (available to all code paths)
    raw_caller = env.get(TOOLI_CALLER, "").strip().lower() or None
    caller_version = env.get(TOOLI_CALLER_VERSION, "").strip() or None
    session_id = env.get(TOOLI_SESSION_ID, "").strip() or None

    # ── Fast path: TOOLI_CALLER convention ─────────────────────────────
    # When the agent explicitly identifies itself, trust it completely.
    if raw_caller:
        display = _TOOLI_CALLER_DISPLAY_NAMES.get(raw_caller, raw_caller)
        desc_parts = [f"TOOLI_CALLER={raw_caller}"]
        if caller_version:
            desc_parts.append(f"v{caller_version}")
        if session_id:
            desc_parts.append(f"session={session_id[:16]}")
        return ExecutionContext(
            category=CallerCategory.AI_AGENT,
            agent_name=display,
            confidence=1.0,
            signals=[" ".join(desc_parts)],
            is_interactive=is_interactive,
            platform=system,
            caller_id=raw_caller,
            caller_version=caller_version,
            session_id=session_id,
        )

    # ── Full heuristic detection ───────────────────────────────────────
    env_signals = _check_env_signatures(env)
    ci_signals = _check_ci(env)
    container_signals = _check_container()
    proc_signals = _check_process_tree()
    stack_signals = _check_call_stack()

    all_signals: list[tuple[str, str, float]] = []
    all_signals.extend(env_signals)
    all_signals.extend(ci_signals)
    all_signals.extend(container_signals)
    all_signals.extend(proc_signals)
    all_signals.extend(stack_signals)

    # Separate positive signals from "negative" (human-indicative) ones
    positive = [(n, d, c) for n, d, c in all_signals if c > 0]
    negative = [(n, d, c) for n, d, c in all_signals if c <= 0]

    signal_descriptions = [desc for _, desc, conf in all_signals if conf > 0]

    # Identify CI and container signal names (these aren't AI agents)
    ci_names = {h[0] for h in ci_signals}
    container_names = {h[0] for h in container_signals}
    non_agent_names = ci_names | container_names | {"Human Shell", "Terminal Emulator"}

    # Find the best CI match
    best_ci: tuple[str, float] | None = None
    if ci_signals:
        best = max(ci_signals, key=lambda x: x[2])
        best_ci = (best[0], best[2])

    # Accumulate confidence for agent signals only (not CI/container)
    agent_scores: dict[str, float] = {}
    for name, _desc, conf in positive:
        if name not in non_agent_names:
            current = agent_scores.get(name, 0.0)
            # First signal sets the baseline; each additional one boosts it
            agent_scores[name] = min(1.0, current + conf * 0.5 if current > 0 else conf)

    best_agent_name: str | None = None
    best_agent_conf: float = 0.0
    if agent_scores:
        best_agent_name = max(agent_scores, key=agent_scores.get)  # type: ignore[arg-type]
        best_agent_conf = agent_scores[best_agent_name]

    # Apply negative signal dampening
    human_dampening = sum(abs(c) for _, _, c in negative)
    best_agent_conf = max(0.0, best_agent_conf - human_dampening * 0.5)

    # Non-interactive terminal is a moderate automation signal
    if not is_interactive and best_agent_conf < 0.5 and best_ci is None:
        signal_descriptions.append("Non-interactive (stdin/stdout not a TTY)")
        best_agent_conf = max(best_agent_conf, 0.3)

    # ----- Classify -----
    if best_ci and (best_ci[1] > best_agent_conf or best_agent_conf < 0.6):
        # CI/CD takes precedence when it's clearly a CI env
        if best_ci[1] >= 0.8:
            return ExecutionContext(
                category=CallerCategory.CI_CD,
                agent_name=best_ci[0],
                confidence=best_ci[1],
                signals=signal_descriptions,
                is_interactive=is_interactive,
                platform=system,
            )

    if best_agent_conf >= 0.7:
        return ExecutionContext(
            category=CallerCategory.AI_AGENT,
            agent_name=best_agent_name,
            confidence=best_agent_conf,
            signals=signal_descriptions,
            is_interactive=is_interactive,
            platform=system,
        )

    # Container-only detection (before generic unknown_automation)
    if container_signals and not is_interactive and best_agent_conf < 0.5:
        best_container = max(container_signals, key=lambda x: x[2])
        return ExecutionContext(
            category=CallerCategory.CONTAINER,
            agent_name=best_container[0],
            confidence=best_container[2],
            signals=[d for _, d, c in container_signals if c > 0],
            is_interactive=is_interactive,
            platform=system,
        )

    if not is_interactive and best_agent_conf > 0.0:
        return ExecutionContext(
            category=CallerCategory.UNKNOWN_AUTOMATION,
            agent_name=best_agent_name,
            confidence=best_agent_conf,
            signals=signal_descriptions,
            is_interactive=is_interactive,
            platform=system,
        )

    return ExecutionContext(
        category=CallerCategory.HUMAN,
        agent_name=None,
        confidence=max(0.0, 1.0 - best_agent_conf),
        signals=signal_descriptions if signal_descriptions else ["Interactive TTY session"],
        is_interactive=is_interactive,
        platform=system,
    )


# ---------------------------------------------------------------------------
# Convenience helpers (for use in _is_agent_mode and output.py)
# ---------------------------------------------------------------------------

_cached_context: ExecutionContext | None = None


def _get_context() -> ExecutionContext:
    """Return the cached detection result (runs detection at most once)."""
    global _cached_context
    if _cached_context is None:
        _cached_context = detect_execution_context()
    return _cached_context


def reset_cache() -> None:
    """Clear the cached context.  Useful in tests."""
    global _cached_context
    _cached_context = None


def is_agent() -> bool:
    """Quick check: is an AI agent running this process?"""
    return _get_context().is_agent


def is_ci() -> bool:
    """Quick check: is a CI/CD pipeline running this process?"""
    return _get_context().is_ci


def is_automation() -> bool:
    """True for any non-human caller (agents, CI, containers, unknown)."""
    return _get_context().category != CallerCategory.HUMAN


def detected_agent_name() -> str | None:
    """Return the specific agent name if detected, else None."""
    ctx = _get_context()
    return ctx.agent_name if ctx.is_agent else None


# ---------------------------------------------------------------------------
# Formatting helpers (used by detect-context builtin command)
# ---------------------------------------------------------------------------

def _format_report(ctx: ExecutionContext) -> str:
    """Format a detection result as a human-readable report."""
    lines = [
        f"Category:      {ctx.category.value}",
        f"Agent Name:    {ctx.agent_name or '(none)'}",
        f"Confidence:    {ctx.confidence:.0%}",
        f"Interactive:   {ctx.is_interactive}",
        f"Platform:      {ctx.platform}",
        f"Convention:    {'Yes' if ctx.identified_via_convention else 'No (heuristic)'}",
    ]
    if ctx.caller_id:
        lines.append(f"Caller ID:     {ctx.caller_id}")
    if ctx.caller_version:
        lines.append(f"Caller Ver:    {ctx.caller_version}")
    if ctx.session_id:
        lines.append(f"Session ID:    {ctx.session_id}")
    lines.append("Signals:")
    for s in ctx.signals:
        lines.append(f"  • {s}")
    if not ctx.signals:
        lines.append("  (none)")
    return "\n".join(lines)


def _format_json(ctx: ExecutionContext) -> str:
    """Format a detection result as JSON."""
    import json
    return json.dumps({
        "category": ctx.category.value,
        "agent_name": ctx.agent_name,
        "confidence": round(ctx.confidence, 3),
        "is_interactive": ctx.is_interactive,
        "is_agent": ctx.is_agent,
        "is_ci": ctx.is_ci,
        "identified_via_convention": ctx.identified_via_convention,
        "caller_id": ctx.caller_id,
        "caller_version": ctx.caller_version,
        "session_id": ctx.session_id,
        "platform": ctx.platform,
        "signals": ctx.signals,
    }, indent=2)
