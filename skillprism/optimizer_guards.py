#!/usr/bin/env python3
"""Anti-pattern guards for the skill optimization loop.

Inspired by darwin-skill's anti-pattern blacklist and SkillOpt's
validation-gated design. These guards run before an edit is applied and
return violations that should block or warn about the candidate change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .evaluate_skill_rubric import SkillReport
from .test_prompts import baseline_dir


@dataclass
class GuardViolation:
    rule: str
    severity: str  # "block" or "warn"
    message: str


# --------------------------------------------------------------------------- #
# Individual guards
# --------------------------------------------------------------------------- #


def guard_one_dimension_per_round(
    baseline: SkillReport,
    candidate: SkillReport,
    threshold: float = 0.5,
) -> Optional[GuardViolation]:
    """A single optimization round should primarily improve one dimension."""
    deltas: Dict[str, float] = {}
    baseline_map = {d.code: d.score for d in baseline.dimensions}
    for d in candidate.dimensions:
        delta = d.score - baseline_map.get(d.code, d.score)
        if abs(delta) >= threshold:
            deltas[d.code] = delta

    improved = [c for c, v in deltas.items() if v > 0]
    regressed = [c for c, v in deltas.items() if v < 0]

    if len(improved) > 1:
        return GuardViolation(
            rule="one_dimension_per_round",
            severity="warn",
            message=f"多个维度同时提升: {improved}。建议每轮只聚焦一个最弱维度，便于归因。",
        )
    if improved and len(regressed) > 1:
        return GuardViolation(
            rule="one_dimension_per_round",
            severity="warn",
            message=f"改进了 {improved}，但多个维度 regress: {regressed}。可能引入副作用。",
        )
    return None


def guard_dry_run_ratio(
    candidate: SkillReport,
    threshold: float = 0.3,
) -> Optional[GuardViolation]:
    """Too many skipped checks means the environment is incomplete."""
    ratio = candidate.dry_run_ratio()
    if ratio > threshold:
        counts = candidate.check_counts()
        return GuardViolation(
            rule="dry_run_ratio",
            severity="warn",
            message=f"干跑比例 {ratio:.0%} ({counts['skipped']}/{counts['total']}) 超过阈值 {threshold:.0%}，"
            "建议先补齐环境/依赖再优化，否则评分不可靠。",
        )
    return None


def guard_no_reset_hard(
    skill_path: Path,
) -> Optional[GuardViolation]:
    """Detect dangerous rollback commands in runnable skill scripts.

    Scoped to executable file types (``.sh``/``.py``) only and excludes
    ``SKILL.md``. The D9 editing strategy instructs the editor to write
    ``git reset --hard`` into SKILL.md as a *forbidden-command example*;
    scanning SKILL.md would self-defeatingly block the very edit the strategy
    mandated. A match in a runnable script is a real hazard and is blocked.
    """
    pattern = re.compile(r"git\s+reset\s+--hard", re.IGNORECASE)
    excluded_parts = {"__pycache__", ".git", ".pytest_cache"}
    risky_files: List[str] = []
    for p in skill_path.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in (".py", ".sh"):
            continue  # only runnable files; SKILL.md docs are exempt
        try:
            rel = p.relative_to(skill_path).parts
        except ValueError:
            continue
        if any(part in excluded_parts for part in rel):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            if pattern.search(text):
                risky_files.append(str(p.relative_to(skill_path)))
        except Exception:
            continue
    if risky_files:
        return GuardViolation(
            rule="no_reset_hard",
            severity="block",
            message=f"发现高危回滚命令 'git reset --hard'，禁止使用。涉及文件: {risky_files}",
        )
    return None


def guard_no_bloat(
    skill_path: Path,
    baseline_report: Optional[Dict[str, Any]] = None,
    line_increase_threshold: float = 0.5,
) -> Optional[GuardViolation]:
    """Detect SKILL.md bloat without meaningful score improvement."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    current_lines = len(skill_md.read_text(encoding="utf-8", errors="replace").splitlines())
    baseline_md = baseline_dir(skill_path) / "SKILL.md"
    if not baseline_md.exists():
        return None

    baseline_lines = len(baseline_md.read_text(encoding="utf-8", errors="replace").splitlines())
    if baseline_lines == 0:
        return None

    increase = (current_lines - baseline_lines) / baseline_lines
    baseline_score = baseline_report.get("score", 0.0) if baseline_report else 0.0
    candidate_score = (
        baseline_report.get("candidate_score", baseline_score)
        if baseline_report
        else baseline_score
    )
    score_gain = candidate_score - baseline_score

    if increase > line_increase_threshold and score_gain < 1.0:
        return GuardViolation(
            rule="no_bloat",
            severity="warn",
            message=f"SKILL.md 行数增加 {increase:.0%}，但分数提升仅 {score_gain:+.1f}。"
            "可能为凑分堆冗余，建议精简。",
        )
    return None


def guard_no_silent_errors(
    candidate: SkillReport,
) -> Optional[GuardViolation]:
    """Ensure evaluation errors are surfaced, not silently swallowed."""
    if candidate.errors:
        return GuardViolation(
            rule="no_silent_errors",
            severity="warn",
            message=f"评估过程中出现 {len(candidate.errors)} 个错误: {'; '.join(candidate.errors[:3])}",
        )
    return None


def guard_self_judge(
    editor_model: Optional[str] = None,
    judge_model: Optional[str] = None,
) -> Optional[GuardViolation]:
    """Warn if the same model edits and judges the skill."""
    if editor_model and judge_model and editor_model == judge_model:
        return GuardViolation(
            rule="self_judge",
            severity="warn",
            message="编辑模型与评分模型相同，可能出现自我偏袒。建议评分使用独立模型或引擎客观测量。",
        )
    return None


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


def run_guards(
    skill_path: Path,
    baseline: SkillReport,
    candidate: SkillReport,
    context: Optional[Dict[str, Any]] = None,
) -> List[GuardViolation]:
    """Run all guards and return a list of violations (blocks + warnings)."""
    ctx = context or {}
    violations: List[GuardViolation] = []

    checks = [
        guard_one_dimension_per_round(baseline, candidate),
        guard_dry_run_ratio(candidate),
        guard_no_reset_hard(skill_path),
        guard_no_bloat(skill_path, ctx.get("baseline_dict")),
        guard_no_silent_errors(candidate),
        guard_self_judge(ctx.get("editor_model"), ctx.get("judge_model")),
    ]

    for v in checks:
        if v:
            violations.append(v)

    return violations


def format_violations(violations: List[GuardViolation]) -> str:
    if not violations:
        return "All anti-pattern guards passed."
    lines = ["### Optimization Guard Report"]
    for v in violations:
        icon = "🚫" if v.severity == "block" else "⚠️"
        lines.append(f"{icon} **{v.rule}** ({v.severity}): {v.message}")
    return "\n".join(lines)
