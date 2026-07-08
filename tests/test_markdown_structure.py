"""Tests for skillprism.markdown_structure."""

from __future__ import annotations

from pathlib import Path

from skillprism.markdown_structure import (
    parse_markdown_structure,
    parse_skill_markdown,
)

SAMPLE = """---
name: test-skill
description: A test skill.
---

# Test Skill

## When to Use

Use this skill for testing.

## Inputs

| Name | Type | Description |
|------|------|-------------|
| path | str | file path |

## Quick Start

```python
print("hello")
```

## Notes

Caution: do not use on large files.
"""


def test_parse_frontmatter() -> None:
    struct = parse_markdown_structure(SAMPLE)
    assert struct.has_frontmatter is True
    assert struct.frontmatter["name"] == "test-skill"


def test_parse_headers() -> None:
    struct = parse_markdown_structure(SAMPLE)
    titles = struct.header_titles()
    assert titles == ["Test Skill", "When to Use", "Inputs", "Quick Start", "Notes"]
    assert struct.max_header_level() == 2
    assert struct.header_hierarchy_ok() is True


def test_header_hierarchy_bad_jump() -> None:
    text = "# A\n### B\n# C\n#### D"
    struct = parse_markdown_structure(text)
    assert struct.header_hierarchy_ok() is False
    assert struct.header_hierarchy_ok(max_skips=2) is True


def test_section_text() -> None:
    struct = parse_markdown_structure(SAMPLE)
    inputs = struct.section_text("Inputs")
    assert "file path" in inputs
    assert "When to Use" not in inputs


def test_section_contains() -> None:
    struct = parse_markdown_structure(SAMPLE)
    assert struct.section_contains("Inputs", ["str", "path"]) is True
    assert struct.section_contains("Inputs", ["missing"]) is False
    assert struct.section_contains("Inputs", ["str", "path"], match_all=True) is True


def test_any_section_contains() -> None:
    struct = parse_markdown_structure(SAMPLE)
    assert struct.any_section_contains(["caution"]) is True


def test_code_blocks() -> None:
    struct = parse_markdown_structure(SAMPLE)
    assert struct.has_code_blocks() is True
    assert struct.code_languages() == ["python"]
    assert 'print("hello")' in struct.code_blocks[0].content


def test_tables() -> None:
    struct = parse_markdown_structure(SAMPLE)
    assert struct.has_tables() is True
    assert struct.tables[0].rows[0] == ["Name", "Type", "Description"]


def test_required_sections() -> None:
    struct = parse_markdown_structure(SAMPLE)
    ok, missing = struct.has_required_sections(["Inputs", "Quick Start"])
    assert ok is True
    ok, missing = struct.has_required_sections(["Outputs"])
    assert ok is False
    assert "Outputs" in missing


def test_empty_document() -> None:
    struct = parse_markdown_structure("")
    assert struct.headers == []
    assert struct.has_code_blocks() is False
    assert struct.has_tables() is False


def test_parse_skill_markdown(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(SAMPLE, encoding="utf-8")
    struct = parse_skill_markdown(skill_dir)
    assert struct.has_frontmatter is True
