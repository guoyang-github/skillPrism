#!/usr/bin/env python3
"""Shared internal helpers (deduplicated across evaluator modules).

Previously ``_read_skill_md``, ``_check_python_syntax``, and ``_list_files*``
were defined verbatim in ``evaluate_skill_rubric.py``, ``skill_lens_checks.py``,
and ``smoke_test_runner.py``. They now live here so the three copies cannot
drift.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

import yaml

# Directories that are never scanned as skill source files.
_EXCLUDED_DIR_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
    ".skillprism_baseline",
}


def read_skill_md(skill_path: Path) -> str:
    """Read SKILL.md text (empty string if absent)."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return ""
    return skill_md.read_text(encoding="utf-8", errors="replace")


def check_python_syntax(path: Path) -> Tuple[bool, str]:
    """Compile-check a Python file; return (ok, error_message)."""
    try:
        import py_compile

        py_compile.compile(str(path), doraise=True)
        return True, ""
    except Exception as e:
        return False, str(e)


def list_files_by_ext(skill_path: Path, exts: List[str]) -> List[Path]:
    """Recursively list files matching one of ``exts``, excluding generated dirs."""
    files: List[Path] = []
    for f in skill_path.rglob("*"):
        if not f.is_file():
            continue
        parts = set(f.parts)
        if parts & _EXCLUDED_DIR_PARTS:
            continue
        if any(str(f).lower().endswith(ext.lower()) for ext in exts):
            files.append(f)
    return files


def _log(text: str, verbose: bool) -> None:
    if verbose:
        print(text)


def _is_skipped_message(text: str) -> bool:
    """Heuristic: a check was skipped if its message mentions skipping."""
    lowered = text.lower()
    return any(k in lowered for k in ["跳过", "skip", "skipped", "not installed", "未安装"])


def _read_frontmatter(skill_path: Path) -> Tuple[Dict[str, Any], bool]:
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return {}, False
    content = skill_md.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(?m)^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
    if not match:
        return {}, False
    try:
        fm = yaml.safe_load(match.group(1)) or {}
        return (fm, True) if isinstance(fm, dict) else ({}, False)
    except yaml.YAMLError:
        return {}, False


def _glob_skill(skill_path: Path, pattern: str) -> List[Path]:
    """Glob relative to a skill directory, returning matching files."""
    parts = pattern.strip("/").split("/")
    if len(parts) == 1:
        return [p for p in skill_path.glob(parts[0]) if p.is_file()]
    base = skill_path
    for part in parts[:-1]:
        base = base / part
    if not base.exists():
        return []
    return [p for p in base.glob(parts[-1]) if p.is_file()]


def _any_file_exists(skill_path: Path, candidates: List[str]) -> bool:
    for c in candidates:
        if (skill_path / c).exists():
            return True
        if _glob_skill(skill_path, c):
            return True
    return False


def _dim_name(code: str, skill_type: str, config: Dict[str, Any]) -> str:
    type_cfg = cast(Dict[str, Any], config.get("skill_types", {}).get(skill_type, {}))
    overrides = cast(Dict[str, str], type_cfg.get("dimension_names_override", {}))
    return overrides.get(code, cast(str, config.get("dimension_names", {}).get(code, code)))
