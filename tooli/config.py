"""Configuration precedence system for Tooli."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:
    import tomli as tomllib # type: ignore[import-not-found, no-redef]


class TooliConfig:
    """Resolves configuration through the precedence chain."""

    def __init__(self, app_name: str = "tooli") -> None:
        self.app_name = app_name
        self._config: dict[str, Any] = {}
        self._load_defaults()
        self._load_project_config()
        self._load_user_config()
        self._load_env_vars()

    def _load_defaults(self) -> None:
        self._config = {
            "output": "auto",
            "no_color": False,
        }

    def _load_project_config(self) -> None:
        """Load from pyproject.toml [tool.tooli]"""
        path = Path("pyproject.toml")
        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = tomllib.load(f)
                    tooli_config = data.get("tool", {}).get("tooli", {})
                    self._config.update(tooli_config)
            except Exception:
                pass

    def _load_user_config(self) -> None:
        """Load from ~/.config/tooli/config.yaml (or toml)"""
        # Simplified: skip yaml/toml for now to avoid extra dependencies
        pass

    def _load_env_vars(self) -> None:
        """Load from TOOLI_* environment variables."""
        for key, value in os.environ.items():
            if key.startswith("TOOLI_"):
                config_key = key[6:].lower()
                # Handle boolean strings
                if value.lower() in ("true", "1", "yes"):
                    self._config[config_key] = True
                elif value.lower() in ("false", "0", "no"):
                    self._config[config_key] = False
                else:
                    self._config[config_key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
