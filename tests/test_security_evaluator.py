#!/usr/bin/env python3
"""Tests for skillprism.security_evaluator."""

from __future__ import annotations

from pathlib import Path

from skillprism.security_evaluator import SecurityFinding, evaluate_d9_security, format_findings


def test_format_findings_empty() -> None:
    assert "No security findings" in format_findings([])


def test_format_findings_table() -> None:
    findings = [
        SecurityFinding(
            id="hardcoded_secret",
            name="硬编码密钥",
            severity="high",
            location="SKILL.md",
            description="Hardcoded secret detected.",
            matched="api_key='abc123'",
        ),
    ]
    md = format_findings(findings)
    assert "### Security Findings" in md
    assert "high" in md
    assert "硬编码密钥" in md


def test_evaluate_d9_security_no_code(tmp_path: Path) -> None:
    skill_dir = tmp_path / "empty-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Safe skill\n", encoding="utf-8")
    score, evidence, suggestions, findings = evaluate_d9_security(skill_dir, "document", {})
    assert isinstance(score, int)
    assert 1 <= score <= 5
    assert findings == []
