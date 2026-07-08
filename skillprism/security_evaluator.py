#!/usr/bin/env python3
"""
Security evaluator for Skill Rubric dimension D9.

Inspired by NVIDIA SkillSpector:
  - Static pattern scanning (regex + AST)
  - Optional external scanner integration (e.g. skillspector)
  - Risk scoring mapped to 1-5 rubric score

Usage:
    from security_evaluator import evaluate_d9_security
    result = evaluate_d9_security(skill_path, skill_type, config)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class SecurityFinding:
    id: str
    name: str
    severity: str  # critical, high, medium, low, info
    location: str
    description: str
    matched: str = ""


SEVERITY_WEIGHT = {
    "critical": 25,
    "high": 15,
    "medium": 5,
    "contextual": 3,  # requires human context; lower impact than unconditional patterns
    "low": 2,
    "info": 0,
}


def _scan_text_for_patterns(text: str, patterns: List[Dict[str, Any]]) -> List[SecurityFinding]:
    findings: List[SecurityFinding] = []
    for group in patterns:
        gid = group.get("id", "unknown")
        name = group.get("name", gid)
        severity = group.get("severity", "medium")
        description = group.get("description", "")
        regexes = group.get("patterns", [])
        for regex in regexes:
            try:
                for match in re.finditer(regex, text, re.IGNORECASE):
                    findings.append(
                        SecurityFinding(
                            id=gid,
                            name=name,
                            severity=severity,
                            location=f"content@offset-{match.start()}",
                            description=description,
                            matched=match.group(0)[:80],
                        )
                    )
            except re.error as exc:
                # A malformed regex in the YAML config previously disabled this
                # pattern silently. Surface it so the config typo is visible.
                print(
                    f"Warning: invalid security regex in group '{gid}' ({regex!r}): {exc}",
                    file=sys.stderr,
                )
                continue
    return findings


def _scan_file(path: Path, patterns: List[Dict[str, Any]]) -> List[SecurityFinding]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"Warning: could not read {path} for security scan: {exc}", file=sys.stderr)
        return []
    findings = _scan_text_for_patterns(text, patterns)
    for f in findings:
        f.location = str(path)
    return findings


def _scan_directory(skill_path: Path, patterns: List[Dict[str, Any]]) -> List[SecurityFinding]:
    findings: List[SecurityFinding] = []
    for p in skill_path.rglob("*"):
        if not p.is_file():
            continue
        if (
            p.name.endswith(".yaml")
            or p.name.endswith(".yml")
            or p.name.endswith(".md")
            or p.name.endswith(".py")
            or p.name.endswith(".sh")
            or p.name.endswith(".R")
            or p.name.endswith(".r")
        ):
            findings.extend(_scan_file(p, patterns))
    return findings


def _run_external_scanner(skill_path: Path, scanner_cfg: Dict[str, Any]) -> List[SecurityFinding]:
    findings: List[SecurityFinding] = []
    command_template = scanner_cfg.get("command", [])
    if not command_template:
        return findings

    command = [
        str(skill_path) if "{skill_path}" in str(part) else part for part in command_template
    ]
    command = [part.replace("{skill_path}", str(skill_path)) for part in command]

    if not shutil.which(command[0]):
        return findings

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
        )
        data = json.loads(proc.stdout)
        # Heuristic: SkillSpector JSON has "findings" or "issues"
        raw_findings = data.get("findings") or data.get("issues") or []
        for item in raw_findings:
            findings.append(
                SecurityFinding(
                    id=item.get("rule_id", item.get("id", "external")),
                    name=item.get("title", item.get("name", "External finding")),
                    severity=(item.get("severity") or "medium").lower(),
                    location=item.get("location", str(skill_path)),
                    description=item.get("description", ""),
                )
            )
    except Exception as exc:
        # A broken external scanner (skillspector installed but failing) would
        # previously yield zero findings silently. Surface the failure.
        print(
            f"Warning: external security scanner failed for {skill_path}: {exc}",
            file=sys.stderr,
        )

    return findings


def _score_from_findings(findings: List[SecurityFinding]) -> int:
    """Map findings to 1-5 rubric score."""
    if not findings:
        return 5

    score = 100
    for f in findings:
        score -= SEVERITY_WEIGHT.get(f.severity, 2)

    if score >= 95:
        return 5
    if score >= 80:
        return 4
    if score >= 60:
        return 3
    if score >= 40:
        return 2
    return 1


def evaluate_d9_security(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
) -> Tuple[int, List[str], List[str], List[SecurityFinding]]:
    """
    Evaluate D9 security for a skill.

    Returns:
        (score, evidence, suggestions, findings)
    """
    security_cfg = config.get("security", {})
    patterns = security_cfg.get("static_patterns", [])
    scanner_cfg = security_cfg.get("external_scanner", {})

    findings: List[SecurityFinding] = []
    evidence: List[str] = []
    suggestions: List[str] = []

    # Static scan
    if patterns:
        findings.extend(_scan_directory(skill_path, patterns))

    # External scanner (optional)
    if scanner_cfg.get("required") or scanner_cfg.get("command"):
        external = _run_external_scanner(skill_path, scanner_cfg)
        findings.extend(external)
        if external:
            evidence.append(f"外部安全扫描器识别 {len(external)} 个问题")

    # Type-specific security keywords in SKILL.md
    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    dim_checks = type_cfg.get("dimension_checks", {}).get("D9", {})
    content = ""
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8", errors="replace").lower()

    sec_keywords = dim_checks.get("security_keywords", ["safe", "sandbox", "read-only"])
    has_security_note = any(k in content for k in sec_keywords)
    if has_security_note:
        evidence.append("SKILL.md 包含安全/稳健性说明")
    else:
        suggestions.append("建议在 SKILL.md 中增加安全使用说明（数据隐私、沙箱、只读等）")

    sensitive_keywords = dim_checks.get("sensitive_data_keywords", [])
    if sensitive_keywords and any(k in content for k in sensitive_keywords):
        evidence.append("SKILL.md 声明了敏感数据处理注意事项")

    if findings:
        critical = sum(1 for f in findings if f.severity == "critical")
        high = sum(1 for f in findings if f.severity == "high")
        medium = sum(1 for f in findings if f.severity == "medium")
        evidence.append(f"静态安全扫描发现: critical={critical}, high={high}, medium={medium}")
        suggestions.append(
            "请审查安全扫描发现，尤其是 critical/high 级别问题，避免环境变量收集、任意代码执行、外部传输等风险。"
        )
    else:
        evidence.append("静态安全扫描未发现明显风险模式")

    score = _score_from_findings(findings)
    # Boost by one point if security notes exist and no critical/high findings
    if has_security_note and not any(f.severity in ("critical", "high") for f in findings):
        score = min(5, score + 1)

    return score, evidence, suggestions, findings


def format_findings(findings: List[SecurityFinding]) -> str:
    lines = ["### Security Findings"]
    if not findings:
        lines.append("No security findings.")
        return "\n".join(lines)
    lines.append("| Severity | ID | Name | Location | Matched |")
    lines.append("|---|---|---|---|---|")
    for f in findings:
        matched = f.matched.replace("|", "\\|")[:40]
        lines.append(f"| {f.severity} | {f.id} | {f.name} | {f.location} | `{matched}` |")
    return "\n".join(lines)
