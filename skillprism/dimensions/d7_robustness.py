#!/usr/bin/env python3
"""Dimension D7: Robustness evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..markdown_structure import parse_skill_markdown
from ..utils import _dim_name
from ..utils import read_skill_md as _read_skill_md

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d7_robustness(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[Any] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import DimensionResult, _score_from_checks

    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    dim_checks = type_cfg.get("dimension_checks", {}).get("D7", {})
    content = _read_skill_md(skill_path).lower()

    if not content:
        return DimensionResult(
            code="D7",
            name=_dim_name("D7", skill_type, config),
            score=3,
            suggestions=["SKILL.md 不存在，无法评估"],
        )

    struct = parse_skill_markdown(skill_path)
    checks: List[Tuple[bool, str, str]] = []

    resource_kw = dim_checks.get("resource_keywords", ["memory", "cpu", "time", "performance"])
    resource_sections = dim_checks.get(
        "resource_sections",
        ["resource", "performance", "requirement", "runtime", "limit"],
    )
    has_resource = struct.section_contains(resource_sections, resource_kw) or any(
        k in content for k in resource_kw
    )
    checks.append((has_resource, "包含资源/性能/运行时间提示", "缺少资源/性能提示"))

    robustness_kw = dim_checks.get("robustness_keywords", ["error", "timeout", "retry", "fallback"])
    robustness_sections = dim_checks.get(
        "robustness_sections",
        ["error", "robustness", "failure", "troubleshooting", "handling"],
    )
    has_robustness = struct.section_contains(robustness_sections, robustness_kw) or any(
        k in content for k in robustness_kw
    )
    checks.append((has_robustness, "包含错误处理/超时/重试/稳健性提示", "缺少稳健性提示"))

    param_sections = dim_checks.get(
        "parameter_sections",
        ["parameter", "参数", "argument", "config", "option"],
    )
    has_param_section = struct.has_header("parameter") or struct.has_header("参数")
    has_param_content = any(struct.section_text(s).strip() for s in param_sections)
    has_params = (has_param_section and has_param_content) or (
        "#" in content and ("parameter" in content or "参数" in content)
    )
    checks.append((has_params, "文档中讨论了关键参数", "未讨论关键参数"))

    result = _score_from_checks(checks)
    result.code = "D7"
    result.name = _dim_name("D7", skill_type, config)
    result.suggestions.append("注：D7 需结合实际运行/使用场景验证")
    return result
