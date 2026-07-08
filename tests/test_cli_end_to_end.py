#!/usr/bin/env python3
"""Smoke tests that the installed CLI entry points are reachable."""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.parametrize(
    "cmd",
    [
        ["evaluate-skill", "--help"],
        ["improve-skill", "--help"],
        ["test-skill", "--help"],
        ["skill-ci", "--help"],
    ],
)
def test_cli_help(cmd: list[str]) -> None:
    """Each registered console script should print help and exit 0."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"{cmd[0]} --help failed: {result.stderr}"
    assert "usage:" in result.stdout.lower()


def test_evaluate_skill_single() -> None:
    """Run the rubric on the built-in skill-prism skill."""
    result = subprocess.run(
        [
            "evaluate-skill",
            "skills/skill-prism",
            "--skills-dir",
            "skills",
            "--config",
            "skill_rubric_types.yaml",
            "--no-generate-prompts",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "Rubric 总分" in result.stdout or "Total score" in result.stdout
