#!/usr/bin/env python3
"""Runtime neutrality checks.

Ensures that a skill is not tied to a single agent runtime (Claude Code,
Cursor, Codex, etc.) so that it can be installed in any skills-compatible
environment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Phrases that strongly tie a skill to a specific runtime.
RUNTIME_SPECIFIC_PATTERNS = [
    # Wording bindings
    r"在 Claude Code",
    r"Claude Code skill",
    r"Claude Code 用户",
    r"Cursor only",
    r"Codex 中",
    r"OpenClaw only",
    r"Gemini CLI only",
    r"Hermes only",
    # Path / install command bindings
    r"~/\.claude/skills/[a-z]",
    r"/plugin install\b",
    r"npx skills add",
    r"npm install -g skills",
    # Badge bindings
    r"Claude Code Skill",
    r"Cursor Only",
    r"Codex Skill",
    # Tool-call bindings without fallback
    r"mcp__claude-in-chrome__",
    r"PostToolUse hook",
]

# Allowed exceptions: trigger words, internal ecosystem references, explicit
# runtime-specific sections, and commit messages are acceptable.
ALLOWED_EXCEPTIONS = [
    r"^---\s*$",  # frontmatter boundary
    r"trigger_words?\s*:",
    r"commit message",
]


@dataclass
class RuntimeNeutralityReport:
    skill_path: Path
    violations: List[str] = field(default_factory=list)
    checked_files: List[str] = field(default_factory=list)

    @property
    def is_neutral(self) -> bool:
        return len(self.violations) == 0


def _is_allowed_line(line: str) -> bool:
    return any(re.search(pattern, line, re.IGNORECASE) for pattern in ALLOWED_EXCEPTIONS)


def check_runtime_neutrality(skill_path: Path) -> RuntimeNeutralityReport:
    """Scan SKILL.md and README.md for runtime-specific wording."""
    report = RuntimeNeutralityReport(skill_path=skill_path)
    checked = ["SKILL.md", "README.md", "README_EN.md"]

    for filename in checked:
        file_path = skill_path / filename
        if not file_path.exists():
            continue
        report.checked_files.append(filename)
        content = file_path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(content.splitlines(), start=1):
            if _is_allowed_line(line):
                continue
            for pattern in RUNTIME_SPECIFIC_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    report.violations.append(
                        f"{filename}:{lineno}: runtime-specific wording: {line.strip()[:80]}"
                    )
                    break

    return report


def format_runtime_neutrality_report(report: RuntimeNeutralityReport) -> str:
    if report.is_neutral:
        return "Runtime neutrality: PASS"
    lines = ["Runtime neutrality: FAIL"] + report.violations
    return "\n".join(lines)
