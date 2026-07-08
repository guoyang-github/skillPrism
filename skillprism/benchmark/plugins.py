#!/usr/bin/env python3
"""Benchmark task plugin registry.

skillPrism supports custom benchmark tasks through two mechanisms:

1. **Entry points**: packages can advertise ``skillprism.benchmark.task`` entry
   points that map a task name to a callable.

2. **Registry plugins**: a benchmark registry YAML can list plugin modules or
   callables under ``plugins`` that are loaded at runtime.

A plugin callable receives the same arguments as the built-in tasks:

    def my_task(
        benchmark: Dict[str, Any],
        skill: str,
        code_path: Optional[Path],
        registry: Dict[str, Any],
        registry_dir: Path,
    ) -> Dict[str, Any]:
        ...

The returned dict should contain at least ``_all_pass`` (bool). Built-in tasks
remain available as fallbacks.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

TaskCallable = Callable[
    [Dict[str, Any], str, Optional[Path], Dict[str, Any], Path],
    Dict[str, Any],
]

_REGISTRY: Dict[str, TaskCallable] = {}


def register(name: str, fn: TaskCallable) -> None:
    """Register a benchmark task by name."""
    _REGISTRY[name] = fn


def unregister(name: str) -> None:
    """Remove a previously registered task."""
    _REGISTRY.pop(name, None)


def clear() -> None:
    """Clear all registered plugins (mainly for tests)."""
    _REGISTRY.clear()


def list_tasks() -> List[str]:
    """Return names of all registered tasks, including built-ins."""
    built_ins = {"clustering", "table", "document", "deconvolution"}
    return sorted(built_ins | set(_REGISTRY.keys()))


def get_task(name: str) -> Optional[TaskCallable]:
    """Return a registered plugin task, or None if not found."""
    return _REGISTRY.get(name)


def _load_entry_points() -> None:
    """Load plugins advertised via ``skillprism.benchmark.task`` entry points."""
    if sys.version_info >= (3, 10):
        from importlib.metadata import entry_points

        eps = entry_points(group="skillprism.benchmark.task")
    else:
        try:
            from importlib_metadata import entry_points
        except ImportError:
            return
        eps = entry_points().get("skillprism.benchmark.task", ())

    for ep in eps:
        try:
            fn = ep.load()
            register(ep.name, fn)
        except Exception:
            # Plugin loading should not break the benchmark runner.
            continue


def _load_module(module_path: str) -> Any:
    """Import a module by dotted path and return the module object."""
    if "." in module_path:
        module_name, attr = module_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, attr)
    return importlib.import_module(module_path)


def load_registry_plugins(registry: Dict[str, Any]) -> None:
    """Load plugins declared in a benchmark registry under ``plugins``."""
    plugins = registry.get("plugins") or []
    for plugin in plugins:
        if isinstance(plugin, str):
            try:
                fn = _load_module(plugin)
                if callable(fn):
                    # Use module-level TASK_NAME if available, else module name.
                    name = getattr(fn, "TASK_NAME", plugin.rsplit(".", 1)[-1])
                    register(name, fn)
            except Exception:
                continue
        elif isinstance(plugin, dict):
            name = plugin.get("name")
            source = plugin.get("source")
            if not name or not source:
                continue
            try:
                fn = _load_module(source)
                if callable(fn):
                    register(name, fn)
            except Exception:
                continue


# Auto-load entry-point plugins on import.
_load_entry_points()
