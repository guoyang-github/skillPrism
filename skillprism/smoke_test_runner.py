#!/usr/bin/env python3
"""
Smoke test runner for Skill executability (D3/D4).

Per-type lightweight checks:
  - analysis: Python/R syntax, attempt to run minimal self-contained examples
  - cmd: shellcheck, command --help smoke checks
  - api: Python syntax, light endpoint probe (if configured)
  - document/generic: template existence, render checks

Usage:
    from smoke_test_runner import run_smoke_tests
    report = run_smoke_tests(skill_path, skill_type, config)
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ._net_guard import is_safe_url
from .benchmark.sandbox import run_script_file
from .utils import check_python_syntax as _check_python_syntax
from .utils import list_files_by_ext as _list_files


@dataclass
class SmokeTest:
    name: str
    passed: bool
    evidence: str = ""
    error: str = ""


@dataclass
class SmokeTestReport:
    skill_name: str
    tests: List[SmokeTest] = field(default_factory=list)
    all_pass: bool = True


# ``_list_files`` and ``_check_python_syntax`` are imported from
# ``skillprism.utils`` above (no local definitions — avoids copy drift).


def _run_python_example(path: Path, timeout: int = 30) -> Tuple[bool, str]:
    """Run a Python example in a sandboxed child process (rlimits + minimal env)."""
    try:
        proc = run_script_file(path, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"example timed out after {timeout}s"
    except Exception as e:
        return False, str(e)
    if proc.returncode == 0:
        return True, "example executed successfully"
    return False, f"exit code {proc.returncode}: {proc.stderr[:200]}"


def _run_shellcheck(path: Path) -> Tuple[bool, str]:
    if not shutil.which("shellcheck"):
        return True, "shellcheck not installed; skipped"
    try:
        proc = subprocess.run(
            ["shellcheck", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return True, "shellcheck passed"
        return False, proc.stdout[:300] + proc.stderr[:300]
    except Exception as e:
        return False, str(e)


def _check_boundary_handling_py(files: List[Path]) -> Tuple[bool, str]:
    """Check whether Python files contain explicit boundary/exception handling."""
    if not files:
        return True, "no Python files to check"
    handlers = ["try:", "except", "raise ", "assert ", "ValueError"]
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if any(h in text for h in handlers):
            return True, f"found boundary/exception handling in {f.name}"
    return False, "no try/except/raise/assert/ValueError found in Python files"


def _check_boundary_handling_sh(files: List[Path]) -> Tuple[bool, str]:
    """Check whether shell scripts contain error handling."""
    if not files:
        return True, "no shell files to check"
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if "set -e" in text or "set -o pipefail" in text or "if [" in text:
            return True, f"found error handling in {f.name}"
    return False, "no set -e / pipefail / conditional error handling found"


def _check_boundary_docs(skill_path: Path) -> Tuple[bool, str]:
    """Check whether SKILL.md mentions boundary cases or error handling."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return True, "SKILL.md missing; skipped"
    content = skill_md.read_text(encoding="utf-8", errors="replace").lower()
    markers = [
        "boundary",
        "edge case",
        "异常",
        "错误处理",
        "error handling",
        "pitfall",
        "troubleshooting",
        "when not to use",
        "limitations",
    ]
    if any(m in content for m in markers):
        return True, "SKILL.md mentions boundary/error handling"
    return False, "SKILL.md does not mention boundary cases, pitfalls, or error handling"


def _probe_api_endpoint(content: str) -> Tuple[bool, str]:
    """Lightweight probe for API endpoint mentioned in docs (curl -I).

    SSRF-guarded: URLs targeting loopback / private / link-local (incl. cloud
    metadata 169.254/16) addresses are skipped via ``is_safe_url``.
    """
    import re

    urls = re.findall(r"https?://[^\s\)\"\'\`\]\>]+", content)
    if not urls:
        return True, "no API endpoint found to probe"
    if not shutil.which("curl"):
        return True, "curl not installed; skipped"
    probed = 0
    for url in urls[:5]:
        if not is_safe_url(url):
            continue
        probed += 1
        try:
            proc = subprocess.run(
                ["curl", "-I", "-s", "-o", "/dev/null", "-w", "%{http_code}", url],
                capture_output=True,
                text=True,
                timeout=15,
            )
            code = proc.stdout.strip()
            if code.startswith("2") or code.startswith("3"):
                return True, f"endpoint {url} returned {code}"
        except Exception:
            continue
    if probed == 0:
        return True, "no safe (public) API endpoint to probe; internal URLs skipped"
    return False, "API endpoints unreachable or returned non-2xx/3xx"


def _extract_example_paths(skill_path: Path) -> List[Path]:
    examples_dir = skill_path / "examples"
    if not examples_dir.is_dir():
        return []
    candidates: List[Path] = []
    for f in examples_dir.rglob("*"):
        if f.is_file() and f.suffix in (".py", ".sh", ".R", ".r"):
            # Prefer files with "minimal", "smoke", or "self" in name
            name = f.name.lower()
            if "minimal" in name or "smoke" in name or "self" in name or "example" in name:
                candidates.insert(0, f)
            else:
                candidates.append(f)
    return candidates


def run_smoke_tests(
    skill_path: Path,
    skill_type: str,
    config: Dict[str, Any],
    verbose: bool = False,
    allow_exec: bool = False,
) -> SmokeTestReport:
    """Run smoke tests.

    ``allow_exec`` gates execution of example scripts. Executing skill-shipped
    code is an opt-in (``--allow-exec``) because it runs code from the skill
    source — syntax/shellcheck/boundary checks always run; example *execution*
    is skipped unless explicitly authorized.
    """
    report = SmokeTestReport(skill_name=skill_path.name)

    if skill_type == "analysis":
        py_files = _list_files(skill_path, [".py"])

        # Python syntax
        for f in py_files:
            ok, err = _check_python_syntax(f)
            report.tests.append(
                SmokeTest(
                    name=f"python syntax: {f.name}",
                    passed=ok,
                    evidence="syntax OK" if ok else "",
                    error=err if not ok else "",
                )
            )

        # Try to run a minimal example (opt-in: executes skill-shipped code)
        example_paths = _extract_example_paths(skill_path)
        if example_paths:
            # Try the shortest example first (likely minimal)
            example_paths.sort(key=lambda p: p.stat().st_size)
            for ex in example_paths[:1]:
                if ex.suffix == ".py":
                    if allow_exec:
                        ok, err = _run_python_example(ex, timeout=30)
                        report.tests.append(
                            SmokeTest(
                                name=f"run example: {ex.name}",
                                passed=ok,
                                evidence="example ran" if ok else "",
                                error=err if not ok else "",
                            )
                        )
                    else:
                        report.tests.append(
                            SmokeTest(
                                name=f"run example: {ex.name}",
                                passed=True,
                                evidence="skipped: pass --allow-exec to execute",
                            )
                        )

        # Boundary / exception handling checks
        ok, err = _check_boundary_handling_py(py_files)
        report.tests.append(
            SmokeTest(
                name="python boundary/exception handling",
                passed=ok,
                evidence=err if ok else "",
                error=err if not ok else "",
            )
        )
        ok, err = _check_boundary_docs(skill_path)
        report.tests.append(
            SmokeTest(
                name="SKILL.md boundary/error handling mention",
                passed=ok,
                evidence=err if ok else "",
                error=err if not ok else "",
            )
        )

    elif skill_type == "cmd":
        sh_files = _list_files(skill_path, [".sh"])
        for f in sh_files:
            ok, err = _run_shellcheck(f)
            report.tests.append(
                SmokeTest(
                    name=f"shellcheck: {f.name}",
                    passed=ok,
                    evidence="shellcheck passed" if ok else "",
                    error=err if not ok else "",
                )
            )

        # Check for set -e / pipefail
        for f in sh_files:
            text = f.read_text(encoding="utf-8", errors="replace")
            has_safety = "set -e" in text or "set -o pipefail" in text
            report.tests.append(
                SmokeTest(
                    name=f"shell safety: {f.name}",
                    passed=has_safety,
                    evidence="set -e / pipefail found" if has_safety else "",
                    error="missing set -e / pipefail" if not has_safety else "",
                )
            )

        # Boundary / exception handling checks
        ok, err = _check_boundary_handling_sh(sh_files)
        report.tests.append(
            SmokeTest(
                name="shell boundary/error handling",
                passed=ok,
                evidence=err if ok else "",
                error=err if not ok else "",
            )
        )
        ok, err = _check_boundary_docs(skill_path)
        report.tests.append(
            SmokeTest(
                name="SKILL.md boundary/error handling mention",
                passed=ok,
                evidence=err if ok else "",
                error=err if not ok else "",
            )
        )

    elif skill_type == "api":
        py_files = _list_files(skill_path, [".py"])
        for f in py_files:
            ok, err = _check_python_syntax(f)
            report.tests.append(
                SmokeTest(
                    name=f"python syntax: {f.name}",
                    passed=ok,
                    evidence="syntax OK" if ok else "",
                    error=err if not ok else "",
                )
            )

        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            ok, err = _probe_api_endpoint(content)
            report.tests.append(
                SmokeTest(
                    name="api endpoint probe",
                    passed=ok,
                    evidence=err if ok else "",
                    error=err if not ok else "",
                )
            )

        # Boundary / exception handling checks
        ok, err = _check_boundary_handling_py(py_files)
        report.tests.append(
            SmokeTest(
                name="api client boundary/exception handling",
                passed=ok,
                evidence=err if ok else "",
                error=err if not ok else "",
            )
        )
        ok, err = _check_boundary_docs(skill_path)
        report.tests.append(
            SmokeTest(
                name="SKILL.md boundary/error handling mention",
                passed=ok,
                evidence=err if ok else "",
                error=err if not ok else "",
            )
        )

    else:  # document / generic
        asset_dirs = ["assets", "templates", "references", "scripts"]
        found = [d for d in asset_dirs if (skill_path / d).is_dir()]
        report.tests.append(
            SmokeTest(
                name="template/asset directories",
                passed=bool(found),
                evidence=f"found: {', '.join(found)}" if found else "",
                error="missing assets/templates/references/scripts directory" if not found else "",
            )
        )

        # Boundary / exception handling docs check
        ok, err = _check_boundary_docs(skill_path)
        report.tests.append(
            SmokeTest(
                name="SKILL.md boundary/error handling mention",
                passed=ok,
                evidence=err if ok else "",
                error=err if not ok else "",
            )
        )

    report.all_pass = all(t.passed for t in report.tests)
    return report


def format_smoke_report(report: SmokeTestReport) -> str:
    lines = ["### Smoke Test Report"]
    if not report.tests:
        lines.append("No smoke tests configured for this skill type.")
        return "\n".join(lines)
    lines.append("| Test | Status | Evidence |")
    lines.append("|---|---|---|")
    for t in report.tests:
        status = "PASS" if t.passed else "FAIL"
        evidence = t.evidence or t.error or "-"
        lines.append(f"| {t.name} | {status} | {evidence} |")
    lines.append("")
    lines.append(f"**All pass**: {report.all_pass}")
    return "\n".join(lines)
