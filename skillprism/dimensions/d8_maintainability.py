#!/usr/bin/env python3
"""Dimension D8: Maintainability evaluator."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..utils import _dim_name
from ..utils import list_files_by_ext as _list_files_by_ext
from ..utils import read_skill_md as _read_skill_md

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d8_maintainability(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[Any] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import _score_from_checks

    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    dim_checks = type_cfg.get("dimension_checks", {}).get("D8", {})
    scripts_dirs = dim_checks.get("scripts_dirs", ["scripts"])
    checks: List[Tuple[bool, str, str]] = []

    has_scripts_dir = any((skill_path / d).is_dir() for d in scripts_dirs)
    checks.append(
        (has_scripts_dir, f"文件按规范目录组织 ({', '.join(scripts_dirs)})", "文件未按规范目录组织")
    )

    py_files = _list_files_by_ext(skill_path, [".py"])
    if py_files and skill_type in {"analysis", "api"}:
        long_funcs = total_funcs = 0
        for f in py_files:
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        total_funcs += 1
                        if len(node.body) > 50:
                            long_funcs += 1
            except Exception:
                pass
        reasonable = total_funcs == 0 or long_funcs / total_funcs <= 0.3
        checks.append(
            (
                reasonable,
                "Python 函数长度合理（无过多超长函数）",
                f"存在 {long_funcs} 个超长函数，建议拆分",
            )
        )

        total_lines = comment_lines = 0
        for f in py_files:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                total_lines += 1
                stripped = line.strip()
                if (
                    stripped.startswith("#")
                    or stripped.startswith('""')
                    or stripped.startswith("''")
                ):
                    comment_lines += 1
        ratio = comment_lines / total_lines if total_lines else 0
        checks.append(
            (
                ratio >= 0.05,
                f"Python 代码注释率 {ratio:.0%}",
                f"Python 代码注释率仅 {ratio:.0%}",
            )
        )

    elif skill_type == "cmd":
        sh_files = _list_files_by_ext(skill_path, [".sh"])
        has_error_handling = False
        for f in sh_files:
            text = f.read_text(encoding="utf-8", errors="replace").lower()
            if "set -e" in text or "set -o pipefail" in text or "log" in text:
                has_error_handling = True
                break
        checks.append(
            (
                has_error_handling,
                "Shell 脚本包含错误处理/日志机制",
                "Shell 脚本缺少 set -e / pipefail / 日志机制",
            )
        )

    else:  # document / generic
        content = _read_skill_md(skill_path).lower()
        has_changelog = any(k in content for k in ["version", "changelog", "更新", "history"])
        checks.append((has_changelog, "包含版本/更新说明", "缺少版本/更新说明"))

    result = _score_from_checks(checks)
    result.code = "D8"
    result.name = _dim_name("D8", skill_type, config)
    return result
