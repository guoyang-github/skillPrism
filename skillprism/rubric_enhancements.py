#!/usr/bin/env python3
"""Rubric scoring enhancements inspired by SkillLens.

These are deterministic, rule-based checks that make the rubric more sensitive
to real quality issues (vague wording, missing failure modes, missing checkpoints,
bloat, etc.). They are run by default during evaluation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .test_prompts import baseline_dir


@dataclass
class QualityIssue:
    check: str
    message: str
    severity: str = "warning"  # warning / error
    count: int = 1


@dataclass
class RubricEnhancements:
    issues: List[QualityIssue] = field(default_factory=list)

    def add(self, check: str, message: str, severity: str = "warning", count: int = 1) -> None:
        self.issues.append(QualityIssue(check, message, severity, count))

    def has_issue(self, check: str) -> bool:
        return any(i.check == check for i in self.issues)

    def score_penalty(self) -> int:
        """Return a suggested total penalty (0-5 scale)."""
        penalty = 0
        for issue in self.issues:
            if issue.severity == "error":
                penalty += min(issue.count, 3)
            else:
                penalty += min(issue.count, 2)
        return min(penalty, 5)


# SkillLens-inspired blacklists
VAGUE_WORDS = [
    "建议",
    "可以考虑",
    "根据情况",
    "灵活把握",
    "视情况而定",
    "酌情",
    "适当",
    "尽量",
    "可能",
    "maybe",
    "consider",
    "perhaps",
    "if appropriate",
    "as needed",
]

AI_BULLSHIT_WORDS = [
    "说白了",
    "换句话说",
    "首先",
    "其次",
    "综上",
    "总而言之",
    "不难发现",
    "显而易见",
    "众所周知",
    "值得注意的是",
    "in conclusion",
    "to summarize",
    "it is important to note",
    "as we all know",
]

EMPTY_TAIL_PHRASES = [
    "灵活应用",
    "根据情况判断",
    "灵活运用",
    "视具体情况而定",
    "灵活运用即可",
]

FAILURE_MODE_PATTERNS = [
    re.compile(r"如果.*失败", re.IGNORECASE),
    re.compile(r"如果.*出错", re.IGNORECASE),
    re.compile(r"if.*fail", re.IGNORECASE),
    re.compile(r"if.*error", re.IGNORECASE),
    re.compile(r"fallback", re.IGNORECASE),
    re.compile(r"else\s*:", re.IGNORECASE),
    re.compile(r"except\s+", re.IGNORECASE),
    re.compile(r"try\s*:", re.IGNORECASE),
]

CHECKPOINT_PATTERNS = [
    re.compile(r"🔴|🛑|⛔|⚠️"),
    re.compile(r"CHECKPOINT|STOP|HALT", re.IGNORECASE),
]


def _count_occurrences(text: str, words: List[str]) -> int:
    count = 0
    lower_text = text.lower()
    for word in words:
        count += lower_text.count(word.lower())
    return count


def _count_regex(text: str, patterns: List[re.Pattern[str]]) -> int:
    count = 0
    for pattern in patterns:
        count += len(pattern.findall(text))
    return count


def _check_empty_tail(description: str) -> List[str]:
    hits = []
    for phrase in EMPTY_TAIL_PHRASES:
        if description.rstrip().endswith(phrase):
            hits.append(phrase)
    return hits


def check_frontmatter(name: str, description: str) -> RubricEnhancements:
    """D1 frontmatter quality checks."""
    result = RubricEnhancements()
    if len(description) > 1024:
        result.add("D1", "description exceeds 1024 characters", severity="warning")
    tail_hits = _check_empty_tail(description)
    if tail_hits:
        result.add(
            "D1",
            f"description ends with empty tail phrase(s): {', '.join(tail_hits)}",
            severity="error",
            count=len(tail_hits),
        )
    if not name or len(name) < 2:
        result.add("D1", "skill name is missing or too short", severity="error")
    return result


def check_documentation_clarity(content: str) -> RubricEnhancements:
    """D2 documentation clarity checks."""
    result = RubricEnhancements()
    vague_count = _count_occurrences(content, VAGUE_WORDS)
    if vague_count > 0:
        result.add(
            "D2",
            f"found {vague_count} vague wording occurrence(s)",
            severity="warning",
            count=vague_count,
        )
    ai_count = _count_occurrences(content, AI_BULLSHIT_WORDS)
    if ai_count > 0:
        result.add(
            "D2",
            f"found {ai_count} AI-bullshit phrase occurrence(s)",
            severity="warning",
            count=ai_count,
        )
    return result


def check_failure_mode_encoding(content: str) -> RubricEnhancements:
    """D3 failure mechanism encoding checks."""
    result = RubricEnhancements()
    failure_count = _count_regex(content, FAILURE_MODE_PATTERNS)
    if failure_count == 0:
        result.add(
            "D3",
            "no explicit failure-mode encoding found (e.g. '如果 X 失败 → Y', fallback, else)",
            severity="error",
        )
    elif failure_count < 2:
        result.add(
            "D3",
            "only one failure-mode branch found; consider adding more fallback paths",
            severity="warning",
        )
    return result


def check_checkpoint_design(content: str) -> RubricEnhancements:
    """D4 checkpoint design checks."""
    result = RubricEnhancements()
    checkpoint_count = _count_regex(content, CHECKPOINT_PATTERNS)
    if checkpoint_count == 0:
        result.add(
            "D4",
            "no explicit checkpoint markers (🔴/🛑/CHECKPOINT/STOP) found",
            severity="error",
        )
    return result


def check_actionable_specificity(content: str) -> RubricEnhancements:
    """D5 actionable specificity checks."""
    result = RubricEnhancements()
    vague_count = _count_occurrences(content, VAGUE_WORDS)
    if vague_count >= 3:
        result.add(
            "D5",
            f"found {vague_count} vague wording occurrence(s) (>=3)",
            severity="error",
            count=vague_count // 3,
        )
    return result


def check_architecture_quality(content: str) -> RubricEnhancements:
    """D7 overall architecture checks."""
    result = RubricEnhancements()
    ai_count = _count_occurrences(content, AI_BULLSHIT_WORDS)
    if ai_count > 0:
        result.add(
            "D7",
            f"found {ai_count} AI-bullshit phrase occurrence(s) in architecture sections",
            severity="warning",
            count=ai_count,
        )
    return result


def check_bloat(
    skill_path: Path, content: str, baseline_path: Path | None = None
) -> RubricEnhancements:
    """D8 maintainability / bloat checks."""
    result = RubricEnhancements()
    current_size = len(content.encode("utf-8"))

    # Compare against original/baseline if available
    if baseline_path and baseline_path.exists():
        original_size = len(baseline_path.read_bytes())
    else:
        original_size = None

    if original_size and original_size > 0:
        ratio = current_size / original_size
        if ratio > 1.5:
            result.add(
                "D8",
                f"SKILL.md size increased to {ratio:.0%} of baseline (>150%)",
                severity="error",
            )
        elif ratio > 1.3:
            result.add(
                "D8",
                f"SKILL.md size increased to {ratio:.0%} of baseline (>130%)",
                severity="warning",
            )

    return result


def evaluate_all(skill_path: Path, content: str, name: str, description: str) -> RubricEnhancements:
    """Run all rubric enhancement checks and merge results."""
    result = RubricEnhancements()
    baseline_path = baseline_dir(skill_path) / "SKILL.md.bak"

    checks = [
        check_frontmatter(name, description),
        check_documentation_clarity(content),
        check_failure_mode_encoding(content),
        check_checkpoint_design(content),
        check_actionable_specificity(content),
        check_architecture_quality(content),
        check_bloat(skill_path, content, baseline_path if baseline_path.exists() else None),
    ]

    for check in checks:
        result.issues.extend(check.issues)

    return result


def format_enhancements_report(enhancements: RubricEnhancements) -> str:
    if not enhancements.issues:
        return "### Quality Issues\n\nNo quality issues detected.\n"

    lines = ["### Quality Issues", ""]
    for issue in enhancements.issues:
        icon = "🔴" if issue.severity == "error" else "⚠️"
        lines.append(f"{icon} **{issue.check}**: {issue.message}")
    lines.append("")
    lines.append(f"**Suggested penalty**: -{enhancements.score_penalty()} points")
    return "\n".join(lines)
