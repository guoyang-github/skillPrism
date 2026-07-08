#!/usr/bin/env python3
"""Tests for skillprism.reports formatting utilities."""

from __future__ import annotations

import json
from pathlib import Path

from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config
from skillprism.reports import (
    _load_baseline_scores,
    format_report_markdown,
    format_scorecard,
    write_history,
)

BASE_SKILL_MD = """---
name: report-test-skill
description: A skill for testing report formatting.
keywords:
  - test
---

# Report Test Skill

## Quick Start

```bash
echo hello
```
"""


def _make_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "report-test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD, encoding="utf-8")
    return skill_dir


def test_format_report_markdown_includes_basic_fields(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg, auto_generate_prompts=False)
    md = format_report_markdown(report, tmp_path, cfg, detailed=False)
    assert report.name in md
    assert "Rubric 总分" in md
    assert "| 维度 |" in md


def test_format_scorecard(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg, auto_generate_prompts=False)
    scorecard = format_scorecard([report], cfg)
    assert "# Skill Scorecard" in scorecard
    assert report.name in scorecard
    assert "D1" in scorecard and "D9" in scorecard


def test_load_baseline_scores_parses_scorecard(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.md"
    scorecard.write_text(
        "# Skill Scorecard\n\n"
        "| Skill | Type | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | Score | Grade |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| foo | analysis | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 52.0 | C |\n",
        encoding="utf-8",
    )
    scores = _load_baseline_scores(scorecard)
    assert scores == {"foo": 52.0}


def test_load_baseline_scores_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _load_baseline_scores(tmp_path / "missing.md") == {}


def test_write_history_appends_jsonl(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, cfg, auto_generate_prompts=False)
    history_path = tmp_path / "history.jsonl"
    write_history([report], cfg, history_path, extra={"source": "test"})
    lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["skill"] == report.name
    assert record["extra"] == {"source": "test"}
