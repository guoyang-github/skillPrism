"""Tests for skillprism.testing.fixtures."""

from __future__ import annotations

from pathlib import Path

from skillprism.testing.fixtures import (
    minimal_registry,
    mock_document_prompt,
    mock_table_csv,
    tmp_skill_dir,
)


def test_tmp_skill_dir(tmp_path: Path) -> None:
    skill_dir = tmp_skill_dir.__wrapped__(tmp_path)
    assert skill_dir.is_dir()
    assert (skill_dir / "SKILL.md").exists()


def test_mock_table_csv(tmp_path: Path) -> None:
    csv_path = mock_table_csv.__wrapped__(tmp_path)
    assert csv_path.exists()
    text = csv_path.read_text(encoding="utf-8")
    assert "col_0" in text
    assert text.startswith("col_0")


def test_mock_document_prompt(tmp_path: Path) -> None:
    prompt_path = mock_document_prompt.__wrapped__(tmp_path)
    assert prompt_path.exists()
    text = prompt_path.read_text(encoding="utf-8")
    assert "skill.md" in text.lower()
    assert "csv summary tool" in text.lower()


def test_minimal_registry() -> None:
    reg = minimal_registry.__wrapped__()
    assert reg["schema_version"] == "2.0"
    assert reg["benchmarks"] == {}
    assert reg["suites"] == {}
