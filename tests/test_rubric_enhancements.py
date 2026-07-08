from pathlib import Path

from skillprism.rubric_enhancements import (
    check_actionable_specificity,
    check_bloat,
    check_checkpoint_design,
    check_documentation_clarity,
    check_failure_mode_encoding,
    check_frontmatter,
)


def test_frontmatter_empty_tail(tmp_path: Path):
    result = check_frontmatter("my-skill", "A skill for testing.灵活应用")
    assert result.has_issue("D1")


def test_frontmatter_description_too_long(tmp_path: Path):
    desc = "x" * 1100
    result = check_frontmatter("my-skill", desc)
    assert result.has_issue("D1")


def test_vague_words(tmp_path: Path):
    content = "你可以建议用户根据情况灵活把握。"
    result = check_documentation_clarity(content)
    assert result.has_issue("D2")


def test_ai_bullshit(tmp_path: Path):
    content = "首先，你需要做 A。其次，做 B。综上，完成。"
    result = check_documentation_clarity(content)
    assert result.has_issue("D2")


def test_missing_failure_mode():
    content = "Step 1: do this. Step 2: do that."
    result = check_failure_mode_encoding(content)
    assert result.has_issue("D3")


def test_failure_mode_present():
    content = "如果 X 失败，执行 Y。"
    result = check_failure_mode_encoding(content)
    assert not any(issue.severity == "error" for issue in result.issues)


def test_missing_checkpoint():
    content = "If unsure, suggest confirming with the user."
    result = check_checkpoint_design(content)
    assert result.has_issue("D4")


def test_checkpoint_present():
    content = "🔴 CHECKPOINT: confirm with the user before proceeding."
    result = check_checkpoint_design(content)
    assert not result.has_issue("D4")


def test_actionable_specificity_threshold():
    content = "建议 A。建议 B。建议 C。"
    result = check_actionable_specificity(content)
    assert result.has_issue("D5")


def test_bloat_guard(tmp_path: Path):
    baseline_dir = tmp_path / ".skillprism_baseline"
    baseline_dir.mkdir()
    baseline_md = baseline_dir / "SKILL.md"
    baseline_md.write_text("x" * 100, encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("x" * 200, encoding="utf-8")
    result = check_bloat(tmp_path, "x" * 200, baseline_path=baseline_md)
    assert result.has_issue("D8")
