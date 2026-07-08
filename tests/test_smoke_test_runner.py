#!/usr/bin/env python3
"""Tests for skillprism.smoke_test_runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, load_config
from skillprism.smoke_test_runner import (
    SmokeTestReport,
    format_smoke_report,
    run_smoke_tests,
)


def _make_analysis_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "analysis-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: analysis-skill
description: test
keywords: [test]
---

# Analysis Skill

## Quick Start

```python
print("hello")
```

## Limitations
Handle boundary cases.
""",
        encoding="utf-8",
    )
    examples = skill_dir / "examples"
    examples.mkdir()
    (examples / "minimal_example.py").write_text(
        "try:\n    print('hello')\nexcept Exception as e:\n    raise ValueError(e)\n",
        encoding="utf-8",
    )
    return skill_dir


def _make_cmd_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "cmd-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: cmd-skill
description: test
keywords: [test]
---
# Cmd Skill
""",
        encoding="utf-8",
    )
    (skill_dir / "run.sh").write_text("#!/bin/bash\nset -e\necho hi", encoding="utf-8")
    return skill_dir


def _make_document_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "document-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: document-skill
description: test
keywords: [test]
---
# Document Skill
""",
        encoding="utf-8",
    )
    templates = skill_dir / "templates"
    templates.mkdir()
    return skill_dir


def _make_api_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "api-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: api-skill
description: test
keywords: [test]
---
# API Skill

Endpoint: https://example.com/api
""",
        encoding="utf-8",
    )
    (skill_dir / "client.py").write_text("import requests\n", encoding="utf-8")
    return skill_dir


def test_run_smoke_tests_analysis_allow_exec(tmp_path: Path) -> None:
    skill_dir = _make_analysis_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = run_smoke_tests(skill_dir, "analysis", cfg, allow_exec=True)
    assert report.skill_name == skill_dir.name
    assert any("python syntax" in t.name for t in report.tests)
    assert any("run example" in t.name for t in report.tests)
    failing = [t for t in report.tests if not t.passed]
    assert not failing, [f"{t.name}: {t.error}" for t in failing]


def test_run_smoke_tests_analysis_no_exec(tmp_path: Path) -> None:
    skill_dir = _make_analysis_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = run_smoke_tests(skill_dir, "analysis", cfg, allow_exec=False)
    assert any("run example" in t.name and "skipped" in t.evidence for t in report.tests)


def test_run_smoke_tests_cmd(tmp_path: Path) -> None:
    skill_dir = _make_cmd_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = run_smoke_tests(skill_dir, "cmd", cfg)
    assert any("shellcheck" in t.name for t in report.tests)
    assert any("shell safety" in t.name for t in report.tests)


def test_run_smoke_tests_document(tmp_path: Path) -> None:
    skill_dir = _make_document_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    report = run_smoke_tests(skill_dir, "document", cfg)
    assert any("template/asset" in t.name for t in report.tests)


def test_run_smoke_tests_api(tmp_path: Path, monkeypatch) -> None:
    skill_dir = _make_api_skill(tmp_path)
    cfg = load_config(DEFAULT_CONFIG)
    # Avoid real curl call.
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/curl")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "200"
        report = run_smoke_tests(skill_dir, "api", cfg)
    assert any("api endpoint" in t.name for t in report.tests)


def test_format_smoke_report() -> None:
    report = SmokeTestReport(skill_name="demo")
    report.tests.append(
        type("T", (), {"name": "t1", "passed": True, "evidence": "ok", "error": ""})()
    )
    text = format_smoke_report(report)
    assert "### Smoke Test Report" in text
    assert "PASS" in text
