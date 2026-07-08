#!/usr/bin/env python3
"""
SkillLens-inspired checks for SKILL.md quality.

Reference: Microsoft Research SkillLens (arXiv 2605.23899)
Three empirically validated dimensions:
  1. Failure Mechanism Encoding  — 显式编码已知失败路径
  2. Actionable Specificity      — 禁用模糊措辞
  3. High-Risk Action Blacklist  — 明文禁止高危操作

These are folded into the existing rubric dimensions:
  - Failure encoding  -> D2 (documentation)
  - Specificity       -> D2 + D6 (LLM callability)
  - Risk blacklist    -> D9 (security)

Usage:
    from skill_lens_checks import evaluate_skill_lens
    result = evaluate_skill_lens(skill_path)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .utils import read_skill_md as _read_skill_md


@dataclass
class SkillLensResult:
    failure_encoding_score: int
    specificity_score: int
    risk_blacklist_score: int
    checkpoint_score: int
    evidence: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


# Section markers that suggest explicit failure-path encoding
FAILURE_SECTION_MARKERS = [
    "pitfall",
    "troubleshooting",
    "failure",
    "error handling",
    "common issue",
    "common mistake",
    "boundary",
    "edge case",
    "反模式",
    "失败模式",
    "故障",
    "边界情况",
    "常见错误",
    "问题排查",
]

FAILURE_PATTERN_MARKERS = [
    "if ... fails",
    "when ... fails",
    "known issue",
    "limitation",
    "not supported",
    "will fail",
    "error:",
    "warning:",
    "deprecated",
    "caveat",
    "caution",
    "avoid",
]

# Vague hedge words that hurt actionable specificity
# Hedge words that signal non-actionable / vague guidance.
# Split by script: Python's ``\b`` is ASCII-word-aware and never matches at a
# CJK boundary, so Chinese hedges must be matched by plain substring.
HEDGE_WORDS_ASCII = [
    "suggest",
    "could consider",
    "depending on",
    "use judgment",
    "case by case",
]
HEDGE_WORDS_CJK = [
    "视情况而定",
    "视需求而定",
    "可以视",
    "建议可以",
    "根据情况",
    "灵活把握",
    "酌情",
    "适当",
    "可能需要",
    "也许",
    "大概",
]

# Explicit checkpoint markers required by darwin-skill dim4
CHECKPOINT_MARKERS = [
    "🔴",
    "🛑",
    "CHECKPOINT",
    "STOP",
    "确认",
]

# High-risk commands/actions that should be explicitly blacklisted
HIGH_RISK_ACTIONS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf *",
    "git reset --hard",
    "git push --force",
    "git push -f",
    "dd if=",
    ":(){ :|:& };:",
    "mkfs.",
    "chmod -R 777 /",
    "chown -R",
    "curl .* | sh",
    "wget .* | sh",
    "curl .* | bash",
    "wget .* | bash",
    "sudo rm",
    "del /f /s /q",
    "format c:",
]


# ``_read_skill_md`` is imported from ``skillprism.utils`` (no local def).


def _has_failure_section(content: str) -> bool:
    # Look for section headers (lines starting with #)
    lines = content.splitlines()
    for line in lines:
        if line.strip().startswith("#"):
            header = line.lower()
            if any(marker in header for marker in FAILURE_SECTION_MARKERS):
                return True
    return False


def _count_failure_patterns(content: str) -> int:
    lower = content.lower()
    return sum(1 for marker in FAILURE_PATTERN_MARKERS if marker.lower() in lower)


def _count_hedge_words(content: str) -> int:
    total = 0
    lower = content.lower()
    for word in HEDGE_WORDS_ASCII:
        total += len(re.findall(r"\b" + re.escape(word.lower()) + r"\b", lower))
    for word in HEDGE_WORDS_CJK:
        # CJK: \b never matches at a CJK boundary, so use plain substring.
        total += lower.count(word.lower())
    return total


def _find_high_risk_actions(content: str) -> List[str]:
    found = []
    lower = content.lower()
    for action in HIGH_RISK_ACTIONS:
        # Use escaped regex for actions with special chars
        pattern = re.escape(action.lower()).replace(r"\*", ".*").replace(r"\.", r"\.")
        if re.search(pattern, lower):
            found.append(action)
    return found


def _has_explicit_checkpoints(content: str) -> bool:
    """Check for explicit checkpoint markers (e.g. 🔴 / STOP / CHECKPOINT)."""
    for marker in CHECKPOINT_MARKERS:
        if marker in content:
            return True
    return False


def evaluate_skill_lens(skill_path: Path) -> SkillLensResult:
    content = _read_skill_md(skill_path)
    lower = content.lower()
    evidence: List[str] = []
    suggestions: List[str] = []

    # 1. Failure Mechanism Encoding
    if not content:
        failure_score = 1
        suggestions.append("SKILL.md 不存在，无法评估失败模式编码")
    else:
        has_section = _has_failure_section(content)
        pattern_count = _count_failure_patterns(content)
        if has_section and pattern_count >= 2:
            failure_score = 5
            evidence.append(f"包含失败模式/边界情况章节，并显式讨论了 {pattern_count} 类失败路径")
        elif has_section or pattern_count >= 2:
            failure_score = 4
            evidence.append("部分包含失败模式说明")
        elif pattern_count == 1:
            failure_score = 3
            suggestions.append("建议单独设立 Pitfalls / Troubleshooting 章节，系统列出已知失败路径")
        else:
            failure_score = 2
            suggestions.append("缺少失败模式/边界情况/反模式说明，LLM 遇到异常时难以自愈")

    # 2. Actionable Specificity
    hedge_count = _count_hedge_words(content)
    if not content:
        specificity_score = 1
        suggestions.append("SKILL.md 不存在，无法评估可执行具体性")
    elif hedge_count == 0:
        specificity_score = 5
        evidence.append("未检测到模糊措辞，指令具体可执行")
    elif hedge_count <= 2:
        specificity_score = 4
        evidence.append(f"仅检测到 {hedge_count} 处模糊措辞")
    elif hedge_count <= 5:
        specificity_score = 3
        suggestions.append(f"检测到 {hedge_count} 处模糊措辞，建议替换为具体参数/步骤")
    else:
        specificity_score = 2
        suggestions.append(f"检测到 {hedge_count} 处模糊措辞，Agent 执行时容易含糊其辞")

    # 3. High-Risk Action Blacklist
    if not content:
        risk_score = 1
        suggestions.append("SKILL.md 不存在，无法评估高风险黑名单")
    else:
        risks = _find_high_risk_actions(content)
        # Check if content has an explicit blacklist section
        has_blacklist_section = any(
            marker in lower
            for marker in ["blacklist", "禁止", "严禁", "do not run", "never run", "high-risk"]
        )
        if risks:
            risk_score = 1
            suggestions.append(f"发现高危操作但未显式禁止: {', '.join(risks)}")
        elif has_blacklist_section:
            risk_score = 5
            evidence.append("包含显式的高风险操作黑名单声明")
        else:
            # No risky commands found, but no explicit blacklist either
            risk_score = 4
            evidence.append("未发现高危操作")
            suggestions.append("建议显式声明高风险操作黑名单（如 rm -rf /、git reset --hard）")

    # 4. Explicit Checkpoint Markers (darwin-skill dim4)
    if not content:
        checkpoint_score = 1
        suggestions.append("SKILL.md 不存在，无法评估检查点设计")
    elif _has_explicit_checkpoints(content):
        checkpoint_score = 5
        evidence.append("包含显性的 🔴/STOP/CHECKPOINT 检查点标记")
    else:
        checkpoint_score = 3
        suggestions.append("建议在关键决策前加入显性检查点标记（如 🔴 CHECKPOINT / 🛑 STOP）")

    return SkillLensResult(
        failure_encoding_score=failure_score,
        specificity_score=specificity_score,
        risk_blacklist_score=risk_score,
        checkpoint_score=checkpoint_score,
        evidence=evidence,
        suggestions=suggestions,
    )


def format_skill_lens_report(result: SkillLensResult) -> str:
    lines = ["### SkillLens Checks"]
    lines.append(f"- Failure mechanism encoding: {result.failure_encoding_score}/5")
    lines.append(f"- Actionable specificity: {result.specificity_score}/5")
    lines.append(f"- High-risk action blacklist: {result.risk_blacklist_score}/5")
    lines.append(f"- Explicit checkpoints: {result.checkpoint_score}/5")
    if result.evidence:
        lines.append("- Evidence:")
        for e in result.evidence:
            lines.append(f"  - {e}")
    if result.suggestions:
        lines.append("- Suggestions:")
        for s in result.suggestions:
            lines.append(f"  - {s}")
    return "\n".join(lines)
