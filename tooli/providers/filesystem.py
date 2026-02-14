"""FileSystem provider loading tools from Python modules."""

from __future__ import annotations

import importlib.util
from types import ModuleType
from pathlib import Path
from typing import TYPE_CHECKING

from tooli.providers.base import Provider
from tooli.transforms import ToolDef

if TYPE_CHECKING:
    from tooli.app import Tooli


class FileSystemProvider(Provider):
    """Loads tool modules from a directory path."""
    
    def __init__(self, directory: str | Path, *, enable_hot_reload: bool = False) -> None:
        self.directory = Path(directory)
        self.enable_hot_reload = enable_hot_reload
        self._loaded_modules: dict[str, ModuleType] = {}
        self._module_mtimes: dict[str, float] = {}
        
    def _module_name(self, path: Path) -> str:
        sanitized = str(path.relative_to(self.directory).as_posix()).replace("/", "_").replace(".", "_")
        return f"tooli_filesystem_{sanitized}"

    def _load_module(self, path: Path) -> ModuleType | None:
        module_name = self._module_name(path)
        mtime = path.stat().st_mtime

        if not self.enable_hot_reload and module_name in self._loaded_modules:
            return self._loaded_modules[module_name]

        if self.enable_hot_reload:
            previous_mtime = self._module_mtimes.get(module_name)
            if previous_mtime is not None and previous_mtime == mtime:
                return self._loaded_modules.get(module_name)

        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            return None

        self._loaded_modules[module_name] = module
        self._module_mtimes[module_name] = mtime
        return module

    def get_tools(self) -> list[ToolDef]:
        tools = []
        if not self.directory.exists():
            return []
            
        for path in self.directory.glob("*.py"):
            if path.name == "__init__.py":
                continue
                
            module = self._load_module(path)
            if module is None:
                continue

            # Look for Tooli command callbacks in the module.
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                cmd_meta = getattr(attr, "__tooli_meta__", None)
                if not callable(attr) or cmd_meta is None:
                    continue

                if attr is module:
                    continue

                name = getattr(attr, "__name__", attr_name)
                tools.append(
                    ToolDef(
                        name=name,
                        callback=attr,
                        help=getattr(attr, "__doc__", None) or "",
                        hidden=getattr(cmd_meta, "hidden", False),
                        tags=[],
                    )
                )

        return tools
