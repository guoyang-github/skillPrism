#!/usr/bin/env python3
"""Optimization strategy library.

Inspired by darwin-skill's P0-P3 strategy library. Strategies are sorted by
priority: runtime/effect issues first, then structure, specificity, and finally
readability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class OptimizationStrategy:
    priority: str  # P0 / P1 / P2 / P3
    id: str
    trigger: str
    action: str
    target_dimensions: List[str]


STRATEGIES: List[OptimizationStrategy] = [
    OptimizationStrategy(
        priority="P0",
        id="runtime_drift",
        trigger="Runtime-specific wording detected (e.g. 'Claude Code', 'Cursor only')",
        action="Replace runtime-specific wording with runtime-neutral alternatives",
        target_dimensions=["D1", "D2"],
    ),
    OptimizationStrategy(
        priority="P0",
        id="effect_regression",
        trigger="Test-prompts verification failed or with-skill worse than without",
        action="Fix the skill's core instructions; reduce over-constraint or ambiguity",
        target_dimensions=["D6", "D8"],
    ),
    OptimizationStrategy(
        priority="P0",
        id="security_regression",
        trigger="D9 security score regressed or high-risk action not blacklisted",
        action="Add explicit blacklist for destructive actions (rm, git reset --hard, force push)",
        target_dimensions=["D9"],
    ),
    OptimizationStrategy(
        priority="P1",
        id="structure",
        trigger="Structural dimensions (D1-D4) are the weakest",
        action="Reorganize workflow into linear steps; add frontmatter trigger words; add checkpoints",
        target_dimensions=["D1", "D2", "D3", "D4"],
    ),
    OptimizationStrategy(
        priority="P2",
        id="specificity",
        trigger="Specificity dimensions (D3, D5) are the weakest",
        action="Add concrete parameters, examples, input/output formats, and failure fallback tables",
        target_dimensions=["D3", "D5"],
    ),
    OptimizationStrategy(
        priority="P2",
        id="failure_mode_encoding",
        trigger="No explicit failure-mode encoding found",
        action="Add if-then fallback tables: trigger condition / first fix / still-fails backup",
        target_dimensions=["D3"],
    ),
    OptimizationStrategy(
        priority="P3",
        id="readability",
        trigger="Readability dimensions (D2, D7, D8) are the weakest",
        action="Split long paragraphs, remove repetition, add TL;DR or decision tree",
        target_dimensions=["D2", "D7", "D8"],
    ),
    OptimizationStrategy(
        priority="P3",
        id="bloat",
        trigger="SKILL.md size > 130% of baseline",
        action="Remove redundant sections; merge duplicate explanations",
        target_dimensions=["D8"],
    ),
]


def get_strategies(
    dimensions: List[Any],
    runtime_warn_count: int = 0,
    prompts_pass_rate: Optional[float] = None,
    security_score: Optional[int] = None,
    bloat_ratio: Optional[float] = None,
    has_failure_modes: bool = True,
) -> List[OptimizationStrategy]:
    """Return applicable strategies sorted by priority."""
    applicable: List[OptimizationStrategy] = []

    # P0: runtime drift
    if runtime_warn_count > 0:
        applicable.append(next(s for s in STRATEGIES if s.id == "runtime_drift"))

    # P0: effect regression
    if prompts_pass_rate is not None and prompts_pass_rate < 0.5:
        applicable.append(next(s for s in STRATEGIES if s.id == "effect_regression"))

    # P0: security regression
    if security_score is not None and security_score <= 2:
        applicable.append(next(s for s in STRATEGIES if s.id == "security_regression"))

    def _code_score(dim: Any) -> Optional[Tuple[str, int]]:
        if isinstance(dim, dict):
            code = dim.get("code")
            score = dim.get("score", 0)
        else:
            code = getattr(dim, "code", None)
            score = getattr(dim, "score", 0)
        if isinstance(code, str) and isinstance(score, int):
            return code, score
        return None

    # Find weakest dimensions
    dim_scores: Dict[str, int] = {}
    for dim in dimensions:
        pair = _code_score(dim)
        if pair:
            dim_scores[pair[0]] = pair[1]

    if not dim_scores:
        return applicable

    weakest_code = min(dim_scores.items(), key=lambda x: x[1])[0]

    # P1: structure
    if weakest_code in ("D1", "D2", "D3", "D4"):
        applicable.append(next(s for s in STRATEGIES if s.id == "structure"))

    # P2: specificity
    if weakest_code in ("D3", "D5"):
        applicable.append(next(s for s in STRATEGIES if s.id == "specificity"))

    # P2: failure mode encoding
    if not has_failure_modes:
        applicable.append(next(s for s in STRATEGIES if s.id == "failure_mode_encoding"))

    # P3: readability
    if weakest_code in ("D2", "D7", "D8"):
        applicable.append(next(s for s in STRATEGIES if s.id == "readability"))

    # P3: bloat
    if bloat_ratio and bloat_ratio > 1.3:
        applicable.append(next(s for s in STRATEGIES if s.id == "bloat"))

    # Sort by priority
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    applicable.sort(key=lambda s: priority_order.get(s.priority, 99))
    return applicable


def format_strategies(strategies: List[OptimizationStrategy]) -> str:
    if not strategies:
        return "No optimization strategies suggested."

    lines = ["### Optimization Strategy (P0-P3)", ""]
    for s in strategies:
        lines.append(f"**{s.priority} · {s.id}**")
        lines.append(f"- Trigger: {s.trigger}")
        lines.append(f"- Action: {s.action}")
        lines.append(f"- Target dimensions: {', '.join(s.target_dimensions)}")
        lines.append("")
    return "\n".join(lines)


def suggest_dimension(dimensions: List[Any]) -> Optional[str]:
    """Return the code of the weakest dimension."""

    def _code_score(dim: Any) -> Optional[Tuple[str, int]]:
        if isinstance(dim, dict):
            code = dim.get("code")
            score = dim.get("score", 0)
        else:
            code = getattr(dim, "code", None)
            score = getattr(dim, "score", 0)
        if isinstance(code, str) and isinstance(score, int):
            return code, score
        return None

    scores: Dict[str, int] = {}
    for dim in dimensions:
        pair = _code_score(dim)
        if pair:
            scores[pair[0]] = pair[1]
    if not scores:
        return None
    return min(scores.items(), key=lambda x: x[1])[0]
