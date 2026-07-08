"""Smoke tests for skill-name-kebab-case."""

import re
from pathlib import Path


def test_skill_md_exists_and_has_frontmatter():
    """SKILL.md must exist and contain a YAML frontmatter block."""
    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    assert skill_md.exists(), "SKILL.md is missing"
    content = skill_md.read_text(encoding="utf-8")
    assert re.search(r"(?m)^---\n.*?\n---", content, re.DOTALL), "SKILL.md missing YAML frontmatter"
