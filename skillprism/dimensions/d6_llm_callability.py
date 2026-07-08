#!/usr/bin/env python3
"""Dimension D6: LLM callability evaluator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..skill_lens_checks import evaluate_skill_lens
from ..utils import _dim_name, _read_frontmatter
from ..utils import read_skill_md as _read_skill_md

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d6_llm_callability(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[Any] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import DimensionResult, _score_from_checks

    content = _read_skill_md(skill_path)
    if not content:
        return DimensionResult(
            code="D6",
            name=_dim_name("D6", skill_type, config),
            score=1,
            suggestions=["SKILL.md 不存在"],
        )

    lower = content.lower()
    frontmatter, _ = _read_frontmatter(skill_path)

    checks: List[Tuple[bool, str, str]] = []

    desc = frontmatter.get("description", "")
    good_desc = isinstance(desc, str) and len(desc.strip()) >= 40
    checks.append(
        (good_desc, "description 字段足够详细（>=40 字符）", "description 过短，Agent 难以匹配")
    )

    keywords = frontmatter.get("keywords", [])
    good_kw = isinstance(keywords, list) and len(keywords) >= 3
    checks.append(
        (
            good_kw,
            f"keywords 数量充足 ({len(keywords) if isinstance(keywords, list) else 0})",
            "keywords 过少",
        )
    )

    has_when_to_use = any(
        k in lower
        for k in ["when to use", "use when", "best for", "recommended", "selection", "选择", "何时"]
    )
    checks.append(
        (
            has_when_to_use,
            "包含何时使用/工具选择说明",
            "缺少何时使用的决策指引",
        )
    )

    if skill_type == "document":
        has_quickstart = any(
            k in lower
            for k in ["two-stage", "stage 1", "stage 2", "template", "outline", "workflow"]
        )
        qs_msg = "包含写作流程/模板/大纲"
        qs_suggest = "缺少写作流程或模板指引"
    else:
        has_quickstart = (
            "quick start" in lower
            or "quickstart" in lower
            or bool(re.search(r"complete\s+\w+\s+pipeline", lower))
            or "workflow" in lower
            or "basic usage" in lower
        )
        qs_msg = "包含 Quick Start / Complete Pipeline / Workflow"
        qs_suggest = "缺少快速上手指南"
    checks.append((has_quickstart, qs_msg, qs_suggest))

    result = _score_from_checks(checks)

    # SkillLens actionable specificity directly impacts LLM callability
    lens = evaluate_skill_lens(skill_path)
    if lens.specificity_score >= 4:
        result.evidence.append("SkillLens: Agent 调用时不易产生模糊措辞")
    else:
        result.suggestions.append(
            f"SkillLens: 文档含模糊措辞，Agent 调用时可能含糊 ({lens.specificity_score}/5)"
        )
        result.score = max(1, result.score - 1)

    result.code = "D6"
    result.name = _dim_name("D6", skill_type, config)
    return result
