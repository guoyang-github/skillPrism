#!/usr/bin/env python3
"""Tests for configurable dimension section lists in skill_rubric_types.yaml."""

from __future__ import annotations

from pathlib import Path

from skillprism.dimensions.d2_documentation import evaluate_d2_documentation
from skillprism.dimensions.d5_domain_accuracy import evaluate_d5_domain_accuracy
from skillprism.dimensions.d7_robustness import evaluate_d7_robustness


def _write_skill(tmp_path: Path, content: str) -> Path:
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


def test_d2_uses_configured_io_sections(tmp_path: Path) -> None:
    skill_dir = _write_skill(
        tmp_path,
        "---\nname: test\ndescription: test\nkeywords: [test]\n---\n\n# Test\n\n## Custom IO\n\nInput: x\nOutput: y\n",
    )
    config = {
        "skill_types": {
            "generic": {
                "dimension_checks": {
                    "D2": {
                        "io_sections": ["custom io"],
                    }
                }
            }
        }
    }
    result = evaluate_d2_documentation(skill_dir, "generic", config)
    assert any("输入/输出" in e for e in result.evidence)


def test_d2_falls_back_to_default_sections(tmp_path: Path) -> None:
    skill_dir = _write_skill(
        tmp_path,
        "---\nname: test\ndescription: test\nkeywords: [test]\n---\n\n# Test\n\n## Input\n\nx\n",
    )
    result = evaluate_d2_documentation(skill_dir, "generic", {})
    assert any("输入/输出" in e for e in result.evidence)


def test_d5_uses_configured_reference_sections(tmp_path: Path) -> None:
    skill_dir = _write_skill(
        tmp_path,
        "---\nname: test\ndescription: test\nkeywords: [test]\n---\n\n# Test\n\n## Sources\n\n- reference 1\n",
    )
    config = {
        "skill_types": {
            "generic": {
                "dimension_checks": {
                    "D5": {
                        "reference_sections": ["sources"],
                    }
                }
            }
        }
    }
    result = evaluate_d5_domain_accuracy(skill_dir, "generic", config)
    assert any("文献" in e for e in result.evidence)


def test_d7_uses_configured_resource_sections(tmp_path: Path) -> None:
    skill_dir = _write_skill(
        tmp_path,
        "---\nname: test\ndescription: test\nkeywords: [test]\n---\n\n# Test\n\n## Resources\n\nUse 8 GB memory.\n",
    )
    config = {
        "skill_types": {
            "generic": {
                "dimension_checks": {
                    "D7": {
                        "resource_sections": ["resources"],
                    }
                }
            }
        }
    }
    result = evaluate_d7_robustness(skill_dir, "generic", config)
    assert any("资源" in e for e in result.evidence)
