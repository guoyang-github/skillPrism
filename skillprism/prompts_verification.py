#!/usr/bin/env python3
"""Test-prompts verification result management.

This module defines the structured exchange format for prompt verification.
The engine itself does not execute prompts; the Agent (or an external script)
runs each prompt with and without the skill, then writes the results to
``{skill_path}/.skillprism_prompts_verification.json``. The engine consumes that
file during evaluation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PromptVerificationResult:
    prompt_id: Any
    prompt: str
    without_skill_output: str
    with_skill_output: str
    expected: str
    improvement_score: float = 0.0
    passed: bool = False
    eval_mode: str = "dry_run"  # full_test / dry_run

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "prompt": self.prompt,
            "without_skill_output": self.without_skill_output,
            "with_skill_output": self.with_skill_output,
            "expected": self.expected,
            "improvement_score": self.improvement_score,
            "passed": self.passed,
            "eval_mode": self.eval_mode,
        }


@dataclass
class PromptsVerificationReport:
    skill: str
    results: List[PromptVerificationResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def all_pass(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    @property
    def dry_run_ratio(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.eval_mode == "dry_run") / len(self.results)

    @property
    def dry_run_warning(self) -> bool:
        return self.dry_run_ratio > 0.3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "pass_rate": self.pass_rate,
                "dry_run_ratio": self.dry_run_ratio,
                "dry_run_warning": self.dry_run_warning,
                **self.summary,
            },
        }


def load_prompts_verification(path: Path) -> Optional[PromptsVerificationReport]:
    """Load a prompts verification report from JSON."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    results = [PromptVerificationResult(**r) for r in data.get("results", [])]
    return PromptsVerificationReport(
        skill=data.get("skill", ""),
        results=results,
        summary=data.get("summary", {}),
    )


def save_prompts_verification(path: Path, report: PromptsVerificationReport) -> Path:
    """Save a prompts verification report to JSON."""
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def format_prompts_verification_report(report: PromptsVerificationReport) -> str:
    """Return a markdown summary of prompt verification results."""
    lines = ["### Test-Prompts Verification"]
    if not report.results:
        lines.append("No prompts verified.")
        return "\n".join(lines)

    lines.append("| Prompt | Passed | Improvement | Mode |")
    lines.append("|---|---|---|---|")
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"| {r.prompt_id} | {status} | {r.improvement_score:.2f} | {r.eval_mode} |")

    lines.append("")
    lines.append(f"**Pass rate**: {report.pass_rate:.0%}")
    lines.append(f"**Dry-run ratio**: {report.dry_run_ratio:.0%}")
    if report.dry_run_warning:
        lines.append(
            "⚠️ **Warning**: dry-run ratio > 30%; measured performance score may be unreliable."
        )
    return "\n".join(lines)
