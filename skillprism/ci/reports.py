#!/usr/bin/env python3
"""Report formatting for CI pipeline runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, cast

import yaml


def _status_emoji(status: bool) -> str:
    return "✅" if status else "❌"


def format_report(results: Dict[str, Any], fmt: str = "markdown") -> str:
    """Render CI pipeline results as markdown, yaml, or json."""
    fmt = fmt.lower()
    if fmt == "json":
        return json.dumps(results, indent=2, ensure_ascii=False)
    if fmt == "yaml":
        return cast(str, yaml.safe_dump(results, allow_unicode=True, sort_keys=False))

    lines = [
        "# Skill CI Report",
        "",
        f"- Skill: `{results.get('skill')}`",
    ]

    if "error" in results:
        lines.extend(["", "## Error", "", f"{results['error']}"])
        lines.extend(
            [
                "",
                "## Summary",
                "",
                f"Overall: {_status_emoji(False)} FAIL",
            ]
        )
        return "\n".join(lines)

    # Static checks
    static = results.get("static", {})
    lines.extend(["", "## Static Checks", ""])

    rubric = static.get("rubric", {})
    if rubric:
        score = rubric.get("score", 0.0)
        grade = rubric.get("grade", "?")
        lines.extend(
            [
                "### Rubric",
                "",
                f"- Score: {score:.1f} / 100",
                f"- Grade: {grade}",
                f"- Skill type: `{rubric.get('skill_type', 'unknown')}`",
                f"- Dimensions: {rubric.get('dimensions', {})}",
                f"- Errors: {rubric.get('errors') or 'none'}",
                "",
            ]
        )

    security = static.get("security", {})
    if security:
        findings = security.get("findings", [])
        lines.extend(
            [
                "### Security",
                "",
                f"- Score: {security.get('score', 0)} / 5",
                f"- Findings: {len(findings)}",
                "",
            ]
        )
        if findings:
            lines.extend(["| Severity | ID | Name | Location |", "|---|---|---|---|"])
            for f in findings:
                lines.append(
                    f"| {f.get('severity', '?')} | {f.get('id', '?')} | "
                    f"{f.get('name', '?')} | {f.get('location', '?')} |"
                )
            lines.append("")

    deps = static.get("dependencies", {})
    if deps:
        lines.extend(
            [
                "### Dependencies",
                "",
                f"- All pass: {_status_emoji(deps.get('all_pass', False))} "
                f"{'PASS' if deps.get('all_pass') else 'FAIL'}",
                "",
            ]
        )
        checks = deps.get("checks", [])
        if checks:
            lines.extend(["| Check | Status | Evidence |", "|---|---|---|"])
            for c in checks:
                passed = c.get("passed", False)
                evidence = c.get("evidence") or c.get("error") or "-"
                lines.append(
                    f"| {c.get('name', '?')} | {_status_emoji(passed)} "
                    f"{'PASS' if passed else 'FAIL'} | {evidence} |"
                )
            lines.append("")

    lines.append(
        f"**Static checks overall**: {_status_emoji(static.get('_all_pass', False))} "
        f"{'PASS' if static.get('_all_pass') else 'FAIL'}"
    )

    # Dynamic benchmark
    benchmark = results.get("benchmark")
    if benchmark:
        lines.extend(
            [
                "",
                "## Benchmarks",
                "",
                "| Benchmark | Status | Notes |",
                "|---|---|---|",
            ]
        )
        for bench_id, bench in benchmark.get("benchmarks", {}).items():
            passed = bool(bench.get("_all_pass"))
            status = f"{_status_emoji(passed)} {'PASS' if passed else 'FAIL'}"
            notes = ""
            if "error" in bench:
                notes = bench["error"]
            elif bench.get("_real_data"):
                notes = "real-data benchmark"
            lines.append(f"| {bench_id} | {status} | {notes} |")

        regression = benchmark.get("_regression")
        if regression:
            lines.extend(
                [
                    "",
                    "## Regression",
                    "",
                    f"- Overall: {_status_emoji(regression.get('all_pass'))} "
                    f"{'PASS' if regression.get('all_pass') else 'FAIL'}",
                    f"- Mock: {_status_emoji(regression.get('mock', {}).get('all_pass'))}",
                    f"- Real data: {_status_emoji(regression.get('real_data', {}).get('all_pass'))}",
                ]
            )

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"Overall: {_status_emoji(bool(results.get('_all_pass')))} "
            f"{'PASS' if results.get('_all_pass') else 'FAIL'}",
        ]
    )
    return "\n".join(lines)


def write_report(report: str, output_path: Path) -> None:
    """Write a rendered report to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
