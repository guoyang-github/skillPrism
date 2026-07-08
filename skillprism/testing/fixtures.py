#!/usr/bin/env python3
"""Pytest fixtures for skillPrism tests.

These fixtures are intended to be used by both skillPrism's own test suite and
by third-party Skill authors who want to test their skills against the rubric
and benchmark framework.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from .mock_data import generate_document_prompt, generate_table_csv


@pytest.fixture
def tmp_skill_dir(tmp_path: Path) -> Path:
    """Create a temporary skill directory with a minimal SKILL.md."""
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: test-skill
description: A minimal test skill.
keywords:
  - test
---

# Test Skill

## When to Use

Use this skill for testing.

## Quick Start

```python
print("hello")
```
""",
        encoding="utf-8",
    )
    return skill_dir


@pytest.fixture
def mock_table_csv(tmp_path: Path) -> Path:
    """Generate a temporary CSV file for table benchmarks."""
    return generate_table_csv(output_path=tmp_path / "input.csv")


@pytest.fixture
def mock_document_prompt(tmp_path: Path) -> Path:
    """Generate a temporary prompt file for document benchmarks."""
    return generate_document_prompt(output_path=tmp_path / "prompt.txt")


@pytest.fixture
def minimal_registry() -> Dict[str, Any]:
    """Return a minimal benchmark registry dictionary."""
    return {
        "schema_version": "2.0",
        "benchmarks": {},
        "suites": {},
    }
