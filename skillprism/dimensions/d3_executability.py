#!/usr/bin/env python3
"""Dimension D3: Executability evaluator."""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..utils import _dim_name
from ..utils import check_python_syntax as _check_python_syntax
from ..utils import list_files_by_ext as _list_files_by_ext
from ..utils import read_skill_md as _read_skill_md

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d3_executability(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[Any] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import _score_from_checks

    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    dim_checks = type_cfg.get("dimension_checks", {}).get("D3", {})
    checks: List[Tuple[bool, str, str]] = []

    if skill_type == "analysis":
        py_files = _list_files_by_ext(skill_path, [".py"])
        r_files = _list_files_by_ext(skill_path, [".R", ".r"])
        has_code = bool(py_files or r_files)
        checks.append(
            (
                has_code,
                f"存在代码文件 (Python {len(py_files)}, R {len(r_files)})",
                "未找到任何 Python/R 代码文件",
            )
        )

        py_ok = sum(1 for f in py_files if _check_python_syntax(f)[0])
        py_all_ok = bool(py_files) and py_ok == len(py_files)
        checks.append(
            (
                py_all_ok,
                f"所有 Python 文件语法正确 ({py_ok}/{len(py_files)})",
                "Python 语法错误或不存在 Python 文件",
            )
        )

        if py_files:
            total_funcs = docstring_funcs = 0
            for f in py_files:
                try:
                    tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            total_funcs += 1
                            if ast.get_docstring(node):
                                docstring_funcs += 1
                except Exception:
                    pass
            ratio = docstring_funcs / total_funcs if total_funcs else 0
            checks.append(
                (
                    ratio >= 0.5,
                    f"Python 函数 docstring 覆盖率 {ratio:.0%}",
                    f"Python 函数 docstring 覆盖率仅 {ratio:.0%}",
                )
            )
        else:
            checks.append((True, "无 Python 代码，跳过 docstring 检查", ""))

    elif skill_type == "cmd":
        sh_files = _list_files_by_ext(skill_path, [".sh"])
        has_shell = bool(sh_files)
        checks.append((has_shell, f"存在 shell 脚本 ({len(sh_files)})", "未找到 shell 脚本"))

        if sh_files and shutil.which("shellcheck"):
            sh_ok = 0
            for f in sh_files:
                try:
                    subprocess.run(
                        ["shellcheck", str(f)], check=True, capture_output=True, timeout=10
                    )
                    sh_ok += 1
                except subprocess.CalledProcessError:
                    pass
            checks.append(
                (
                    sh_ok == len(sh_files),
                    f"shellcheck 通过 ({sh_ok}/{len(sh_files)})",
                    f"shellcheck 在 {len(sh_files) - sh_ok} 个脚本中报告问题",
                )
            )
        elif sh_files:
            checks.append(
                (True, "shellcheck 未安装，跳过；建议安装", "建议安装 shellcheck 做语法检查")
            )

        content = _read_skill_md(skill_path).lower()
        resource_keywords = dim_checks.get("resource_keywords", ["cpu", "gpu", "memory", "threads"])
        has_resources = any(k in content for k in resource_keywords)
        checks.append((has_resources, "包含 CPU/GPU/内存/运行时间提示", "缺少资源/运行时间提示"))

    elif skill_type == "api":
        py_files = _list_files_by_ext(skill_path, [".py"])
        has_client = bool(py_files)
        checks.append(
            (
                has_client,
                f"存在 API 客户端/示例代码 ({len(py_files)} Python)",
                "未找到 API 客户端或示例代码",
            )
        )

        py_ok = sum(1 for f in py_files if _check_python_syntax(f)[0])
        py_all_ok = bool(py_files) and py_ok == len(py_files)
        checks.append(
            (
                py_all_ok,
                f"Python 客户端语法正确 ({py_ok}/{len(py_files)})",
                "Python 客户端存在语法错误",
            )
        )

        content = _read_skill_md(skill_path).lower()
        has_endpoint = "https://" in content or "endpoint" in content or "rest." in content
        checks.append((has_endpoint, "文档中包含 API endpoint 示例", "缺少 API endpoint 示例"))
        has_auth = any(k in content for k in ["api key", "auth", "token", "认证"])
        checks.append((has_auth, "包含认证/权限说明", "缺少认证说明（如公开 API 可忽略）"))

    else:  # document or generic
        asset_dirs = dim_checks.get("scripts_dirs", ["assets", "templates", "references"])
        has_assets = any((skill_path / d).is_dir() for d in asset_dirs)
        checks.append((has_assets, "存在模板/素材/参考文献目录", "缺少模板或素材目录"))

        content = _read_skill_md(skill_path).lower()
        has_style = any(
            k in content for k in ["format", "template", "style", "guideline", "imrad", "结构"]
        )
        checks.append((has_style, "包含写作结构/格式规范", "缺少写作结构或格式规范"))
        has_examples = "example" in content or "template" in content or "sample" in content
        checks.append((has_examples, "包含示例输出或模板片段", "缺少示例输出"))

    result = _score_from_checks(checks)
    result.code = "D3"
    result.name = _dim_name("D3", skill_type, config)
    return result
