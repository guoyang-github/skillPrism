#!/usr/bin/env python3
"""Dimension D9: Security evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from ..security_evaluator import evaluate_d9_security
from ..skill_lens_checks import evaluate_skill_lens
from ..utils import _dim_name

if TYPE_CHECKING:
    from ..evaluate_skill_rubric import DimensionResult


def evaluate_d9_security_dimension(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    llm_judge: Optional[Any] = None,
) -> DimensionResult:
    from ..evaluate_skill_rubric import DimensionResult

    score, evidence, suggestions, findings = evaluate_d9_security(skill_path, skill_type, config)

    # SkillLens high-risk action blacklist check
    lens = evaluate_skill_lens(skill_path)
    if lens.risk_blacklist_score >= 4:
        evidence.append("SkillLens: 高风险操作黑名单声明充分")
    else:
        suggestions.append(f"SkillLens: 高风险操作黑名单声明不足 ({lens.risk_blacklist_score}/5)")

    # Merge scores: if either security scan or SkillLens risk is low, cap the result
    if lens.risk_blacklist_score <= 2:
        score = min(score, 2)
    elif lens.risk_blacklist_score == 3:
        score = min(score, 4)

    result = DimensionResult(
        code="D9",
        name=_dim_name("D9", skill_type, config),
        score=score,
        evidence=evidence,
        suggestions=suggestions,
    )
    return result
