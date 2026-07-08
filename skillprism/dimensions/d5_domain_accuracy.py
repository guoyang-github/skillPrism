#!/usr/bin/env python3
"""Dimension D5: Domain accuracy evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..llm_judge import LLMJudge, blend_score, judge_dimension, judge_dimension_multi
from ..markdown_structure import parse_skill_markdown
from ..utils import _dim_name
from ..utils import read_skill_md as _read_skill_md

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d5_domain_accuracy(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[LLMJudge] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import DimensionResult, _score_from_checks

    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    dim_checks = type_cfg.get("dimension_checks", {}).get("D5", {})
    raw_content = _read_skill_md(skill_path)
    content = raw_content.lower()

    if not content:
        return DimensionResult(
            code="D5",
            name=_dim_name("D5", skill_type, config),
            score=3,
            suggestions=["SKILL.md 不存在，无法自动评估；需人工评审"],
        )

    struct = parse_skill_markdown(skill_path)
    checks: List[Tuple[bool, str, str]] = []

    ref_keywords = dim_checks.get(
        "reference_keywords", ["reference", "文献", "citation", "guideline"]
    )
    ref_sections = dim_checks.get(
        "reference_sections",
        ["reference", "bibliography", "literature", "guideline"],
    )
    has_ref = struct.section_contains(ref_sections, ref_keywords) or any(
        k in content for k in ref_keywords
    )
    checks.append((has_ref, "包含 References / 文献/指南引用", "缺少文献/指南引用"))

    accuracy_kw = dim_checks.get("accuracy_keywords", ["parameter", "recommended", "推荐"])
    accuracy_sections = dim_checks.get(
        "accuracy_sections",
        ["parameter", "method", "best practice", "recommendation", "setting"],
    )
    has_accuracy = struct.section_contains(accuracy_sections, accuracy_kw) or any(
        k in content for k in accuracy_kw
    )
    checks.append((has_accuracy, "包含参数/方法/最佳实践说明", "缺少参数或最佳实践说明"))

    pitfall_kw = dim_checks.get("pitfall_keywords", ["pitfall", "caution", "注意", "警告"])
    pitfall_sections = dim_checks.get(
        "pitfall_sections",
        ["pitfall", "caution", "warning", "troubleshooting", "caveat", "note"],
    )
    has_pitfalls = struct.section_contains(pitfall_sections, pitfall_kw) or any(
        k in content for k in pitfall_kw
    )
    checks.append((has_pitfalls, "包含陷阱/注意事项提示", "缺少陷阱/注意事项提示"))

    result = _score_from_checks(checks)

    # Optional LLM-as-judge for subjective domain accuracy
    if llm_judge is not None:
        if llm_judge.n_judges > 1:
            multi_result = judge_dimension_multi(llm_judge, "D5", raw_content, result.score)
            if multi_result and multi_result.aggregated_score > 0:
                blended = blend_score(result.score, multi_result.aggregated_score, llm_judge.weight)
                result.evidence.append(
                    f"LLM judges: {multi_result.scores} (aggregate={multi_result.aggregate}, "
                    f"score={multi_result.aggregated_score}) blended to {blended}/5"
                )
                result.score = blended
        else:
            llm_result = judge_dimension(llm_judge, "D5", raw_content, result.score)
            if llm_result and llm_result.score > 0:
                blended = blend_score(result.score, llm_result.score, llm_judge.weight)
                result.evidence.append(
                    f"LLM judge: {llm_result.score}/5 (blended to {blended}/5): {llm_result.reason}"
                )
                result.score = blended

    result.code = "D5"
    result.name = _dim_name("D5", skill_type, config)
    result.suggestions.append("注：D5 需领域专家最终人工复核")
    return result
