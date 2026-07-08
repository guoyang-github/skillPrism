#!/usr/bin/env python3
"""Tests for pipeline gradual test integration and test-skill wrapper."""

from __future__ import annotations

from pathlib import Path

from skillprism.orchestrator import run_gradual_all, run_gradual_for_skill

from .benchmark_helpers import (
    make_benchmark_entry,
    make_pass_through_code,
    make_table_csv,
    write_registry,
)


def test_run_gradual_for_skill(tmp_path: Path) -> None:
    input_csv = make_table_csv(tmp_path, "data", [["x", "y"], ["1", "2"]])
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "table_unit": make_benchmark_entry(
                tmp_path,
                "table_unit",
                "Table Unit",
                "my-skill",
                "table",
                input_csv,
                code_path,
                level=0,
            ),
        },
    }
    registry_path = write_registry(tmp_path, registry)
    result = run_gradual_for_skill(
        skill_name="my-skill",
        skill_type="my-skill",
        registry_path=registry_path,
        output_dir=tmp_path / "out",
        max_level=0,
        ratchet=False,
        code_path=code_path,
    )
    assert result["_all_pass"] is True
    assert "level0" in result["stages"]


def test_run_gradual_all(tmp_path: Path) -> None:
    input_csv = make_table_csv(tmp_path, "data", [["x", "y"], ["1", "2"]])
    code_path = make_pass_through_code(tmp_path)
    registry = {
        "schema_version": "1.0",
        "benchmarks": {
            "table_unit": make_benchmark_entry(
                tmp_path,
                "table_unit",
                "Table Unit",
                "my-skill",
                "table",
                input_csv,
                code_path,
                level=0,
            ),
        },
    }
    registry_path = write_registry(tmp_path, registry)

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: Test\nkeywords: [test]\ntool_type: python\n---\n\n# Test\n",
        encoding="utf-8",
    )

    config = {
        "skill_types": {
            "my-skill": {
                "detection": {
                    "keywords": ["my-skill"],
                }
            }
        }
    }
    results = run_gradual_all(
        skills_dir=tmp_path,
        registry_path=registry_path,
        output_dir=tmp_path / "out",
        config=config,
        max_level=0,
        ratchet=False,
        code_path=code_path,
    )
    assert results["my-skill"]["_all_pass"] is True
