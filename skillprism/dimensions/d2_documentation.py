#!/usr/bin/env python3
"""Dimension D2: Documentation evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..llm_judge import LLMJudge, blend_score, judge_dimension, judge_dimension_multi
from ..markdown_structure import parse_skill_markdown
from ..skill_lens_checks import evaluate_skill_lens
from ..utils import _dim_name
from ..utils import read_skill_md as _read_skill_md

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d2_documentation(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[LLMJudge] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import DimensionResult, _score_from_checks

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return DimensionResult(
            code="D2",
            name=_dim_name("D2", skill_type, config),
            score=1,
            suggestions=["SKILL.md 不存在，无法评估文档"],
        )

    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    dim_checks = type_cfg.get("dimension_checks", {}).get("D2", {})
    content = _read_skill_md(skill_path)
    lower = content.lower()
    struct = parse_skill_markdown(skill_path)

    checks: List[Tuple[bool, str, str]] = []

    has_overview = (
        struct.has_frontmatter
        and any(h.level == 1 for h in struct.headers)
        and struct.document_length_ok()
        and struct.header_hierarchy_ok()
    )
    checks.append((has_overview, "文档结构完整（有标题、正文）", "文档过短或结构异常"))

    io_keywords = dim_checks.get("io_keywords", ["input", "output", "parameter"])
    io_sections = dim_checks.get(
        "io_sections",
        ["input", "output", "parameter", "usage", "arguments", "signature"],
    )
    has_io = struct.section_contains(io_sections, io_keywords) or any(
        k in lower for k in io_keywords
    )
    checks.append((has_io, "包含输入/输出或使用说明", "缺少输入输出说明"))

    code_markers = dim_checks.get("code_example_markers", ["```"])
    has_examples = struct.has_code_blocks() or any(m in content for m in code_markers)
    checks.append((has_examples, "包含可运行示例或模板", "缺少示例或模板"))

    has_table = struct.has_tables() or "|" in content
    checks.append((has_table, "使用表格组织信息", "缺少表格，可读性受限"))

    version_sections = dim_checks.get(
        "version_sections",
        ["version", "compatibility", "requirements", "dependencies"],
    )
    has_version = struct.section_contains(version_sections, ["version", "兼容", "api version"]) or (
        "version" in lower or "兼容" in lower or "api version" in lower
    )
    checks.append((has_version, "包含版本/兼容性说明", "缺少版本兼容性说明"))

    pitfall_sections = dim_checks.get(
        "pitfall_sections",
        ["pitfall", "troubleshooting", "caveat", "common issue", "注意", "warning"],
    )
    pitfall_keywords = [
        "pitfall",
        "troubleshooting",
        "common issue",
        "注意",
        "警告",
        "deprecated",
        "caution",
        "common mistakes",
    ]
    has_pitfalls = struct.section_contains(pitfall_sections, pitfall_keywords) or any(
        k in lower for k in pitfall_keywords
    )
    checks.append((has_pitfalls, "包含 pitfalls 或 troubleshooting 说明", "缺少常见问题/陷阱提示"))

    result = _score_from_checks(checks)

    # Integrate SkillLens failure encoding + actionable specificity
    lens = evaluate_skill_lens(skill_path)
    if lens.failure_encoding_score >= 4:
        result.evidence.append("SkillLens: 失败模式编码充分")
    else:
        result.suggestions.append(f"SkillLens: 失败模式编码不足 ({lens.failure_encoding_score}/5)")
    if lens.specificity_score >= 4:
        result.evidence.append("SkillLens: 可执行具体性良好")
    else:
        result.suggestions.append(
            f"SkillLens: 包含模糊措辞，可执行具体性 {lens.specificity_score}/5"
        )

    if lens.failure_encoding_score >= 4 and lens.specificity_score >= 4:
        result.score = min(5, result.score + 1)
    elif lens.failure_encoding_score <= 2 or lens.specificity_score <= 2:
        result.score = max(1, result.score - 1)

    # Optional LLM-as-judge for subjective documentation quality
    if llm_judge is not None:
        if llm_judge.n_judges > 1:
            multi_result = judge_dimension_multi(llm_judge, "D2", content, result.score)
            if multi_result and multi_result.aggregated_score > 0:
                blended = blend_score(result.score, multi_result.aggregated_score, llm_judge.weight)
                result.evidence.append(
                    f"LLM judges: {multi_result.scores} (aggregate={multi_result.aggregate}, "
                    f"score={multi_result.aggregated_score}) blended to {blended}/5"
                )
                result.score = blended
        else:
            llm_result = judge_dimension(llm_judge, "D2", content, result.score)
            if llm_result and llm_result.score > 0:
                blended = blend_score(result.score, llm_result.score, llm_judge.weight)
                result.evidence.append(
                    f"LLM judge: {llm_result.score}/5 (blended to {blended}/5): {llm_result.reason}"
                )
                result.score = blended

    result.code = "D2"
    result.name = _dim_name("D2", skill_type, config)
    return result
