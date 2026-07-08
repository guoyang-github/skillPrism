#!/usr/bin/env python3
"""
Dependency reproducibility checker for Skill dimension D4.

Checks:
  - requirements.txt existence and parseability
  - environment.yml existence and parseability
  - Dockerfile existence
  - Optional: pip install --dry-run (slow, use --check-deps to enable)
  - Optional: conda env create --dry-run (if conda available)

Usage:
    from dependency_checker import check_dependencies
    report = check_dependencies(skill_path, skill_type, config)
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class DependencyCheck:
    name: str
    passed: bool
    evidence: str = ""
    error: str = ""


@dataclass
class DependencyReport:
    skill_name: str
    checks: List[DependencyCheck] = field(default_factory=list)
    all_pass: bool = True


def _parse_requirements(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _pip_dry_run(path: Path) -> Tuple[bool, str]:
    if not shutil.which("pip"):
        return True, "pip not available; skipped"
    try:
        proc = subprocess.run(
            ["python", "-m", "pip", "install", "--dry-run", "--ignore-installed", "-r", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            return True, "pip dry-run succeeded"
        return False, (proc.stdout + proc.stderr)[:400]
    except subprocess.TimeoutExpired:
        return False, "pip dry-run timed out"
    except Exception as e:
        return False, str(e)


def _conda_dry_run(path: Path) -> Tuple[bool, str]:
    if not shutil.which("conda"):
        return True, "conda not available; skipped"
    try:
        proc = subprocess.run(
            ["conda", "env", "create", "--file", str(path), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode == 0:
            return True, "conda dry-run succeeded"
        return False, (proc.stdout + proc.stderr)[:400]
    except subprocess.TimeoutExpired:
        return False, "conda dry-run timed out"
    except Exception as e:
        return False, str(e)


def check_dependencies(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    run_dry_run: bool = False,
) -> DependencyReport:
    report = DependencyReport(skill_name=skill_path.name)

    req_path = skill_path / "requirements.txt"
    if req_path.exists():
        try:
            deps = _parse_requirements(req_path)
            pinned = any(
                "==" in line or ">=" in line or "<=" in line or "~=" in line for line in deps
            )
            report.checks.append(
                DependencyCheck(
                    name="requirements.txt parseable",
                    passed=True,
                    evidence=f"{len(deps)} dependencies listed",
                )
            )
            report.checks.append(
                DependencyCheck(
                    name="requirements.txt has version constraints",
                    passed=pinned,
                    evidence="version constraints present" if pinned else "",
                    error="no version constraints found" if not pinned else "",
                )
            )
            if run_dry_run:
                ok, err = _pip_dry_run(req_path)
                report.checks.append(
                    DependencyCheck(
                        name="pip install --dry-run",
                        passed=ok,
                        evidence=err if ok else "",
                        error=err if not ok else "",
                    )
                )
        except Exception as e:
            report.checks.append(
                DependencyCheck(
                    name="requirements.txt parseable",
                    passed=False,
                    error=str(e),
                )
            )

    env_path = skill_path / "environment.yml"
    if env_path.exists():
        try:
            import yaml

            with env_path.open("r", encoding="utf-8") as f:
                yaml.safe_load(f)
            report.checks.append(
                DependencyCheck(
                    name="environment.yml parseable",
                    passed=True,
                    evidence="valid YAML",
                )
            )
            if run_dry_run:
                ok, err = _conda_dry_run(env_path)
                report.checks.append(
                    DependencyCheck(
                        name="conda env create --dry-run",
                        passed=ok,
                        evidence=err if ok else "",
                        error=err if not ok else "",
                    )
                )
        except Exception as e:
            report.checks.append(
                DependencyCheck(
                    name="environment.yml parseable",
                    passed=False,
                    error=str(e),
                )
            )

    docker_path = skill_path / "Dockerfile"
    if docker_path.exists():
        report.checks.append(
            DependencyCheck(
                name="Dockerfile present",
                passed=True,
                evidence="Dockerfile found",
            )
        )

    # R DESCRIPTION / renv.lock
    desc_path = skill_path / "DESCRIPTION"
    renv_lock = skill_path / "renv.lock"
    if desc_path.exists() or renv_lock.exists():
        report.checks.append(
            DependencyCheck(
                name="R dependency file present",
                passed=True,
                evidence=f"found: {', '.join(p.name for p in [desc_path, renv_lock] if p.exists())}",
            )
        )

    report.all_pass = all(c.passed for c in report.checks)
    return report


def format_dependency_report(report: DependencyReport) -> str:
    lines = ["### Dependency Reproducibility Report"]
    if not report.checks:
        lines.append("No dependency files found.")
        return "\n".join(lines)
    lines.append("| Check | Status | Evidence |")
    lines.append("|---|---|---|")
    for c in report.checks:
        status = "PASS" if c.passed else "FAIL"
        evidence = c.evidence or c.error or "-"
        lines.append(f"| {c.name} | {status} | {evidence} |")
    lines.append("")
    lines.append(f"**All pass**: {report.all_pass}")
    return "\n".join(lines)
