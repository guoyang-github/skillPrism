#!/usr/bin/env python3
"""Dimension D1: Structure evaluator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..utils import _any_file_exists, _dim_name, _read_frontmatter

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d1_structure(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[Any] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import _score_from_checks

    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    checks: List[Tuple[bool, str, str]] = []

    skill_md = skill_path / "SKILL.md"
    checks.append((skill_md.exists(), "SKILL.md exists", "缺少 SKILL.md"))

    frontmatter, fm_ok = _read_frontmatter(skill_path)
    checks.append((fm_ok, "Frontmatter 可解析", "SKILL.md frontmatter 解析失败"))

    required_base = set(config.get("required_frontmatter_base", []))
    missing_base = required_base - set(frontmatter.keys())
    checks.append(
        (
            not missing_base,
            f"包含基础必需 frontmatter 字段: {', '.join(sorted(required_base))}",
            f"缺少基础必需 frontmatter 字段: {missing_base}",
        )
    )

    recommended = set(type_cfg.get("frontmatter_recommended", []))
    missing_rec = recommended - set(frontmatter.keys())
    if recommended:
        checks.append(
            (
                not missing_rec,
                f"包含类型推荐 frontmatter 字段 ({skill_type}): {', '.join(sorted(recommended))}",
                f"缺少类型推荐 frontmatter 字段: {missing_rec}",
            )
        )

    name_ok = False
    if isinstance(frontmatter.get("name"), str):
        name = frontmatter["name"]
        name_ok = bool(re.match(r"^[a-z0-9-]+$", name)) and not (
            name.startswith("-") or name.endswith("-") or "--" in name
        )
    checks.append((name_ok, "name 符合 kebab-case 命名规范", "name 命名不规范"))

    d1_checks = type_cfg.get("dimension_checks", {}).get("D1", {})

    if d1_checks.get("require_examples", True):
        examples_dir = skill_path / "examples"
        has_examples = examples_dir.is_dir() and any(examples_dir.iterdir())
        checks.append((has_examples, "examples/ 目录存在且非空", "缺少 examples/ 目录或示例"))

    dep_candidates = d1_checks.get("dependency_file_candidates", [])
    has_dep_file = _any_file_exists(skill_path, dep_candidates) if dep_candidates else True
    if dep_candidates:
        checks.append(
            (
                has_dep_file,
                f"存在类型相关依赖/资源文件 ({skill_type})",
                f"缺少类型相关依赖/资源文件: {dep_candidates}",
            )
        )

    if d1_checks.get("require_usage_guide", True):
        has_usage_guide = (skill_path / "usage-guide.md").exists() or (
            skill_path / "README.md"
        ).exists()
        checks.append((has_usage_guide, "存在 usage-guide.md 或 README.md", "缺少用户使用指南"))

    result = _score_from_checks(checks)
    result.code = "D1"
    result.name = _dim_name("D1", skill_type, config)
    return result
