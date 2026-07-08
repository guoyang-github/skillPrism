"""Tests for skillprism.evaluate_skill_rubric CLI helpers and main()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from skillprism.evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    DimensionResult,
    _build_evaluate_parser,
    _check_ratchet,
    _load_baseline_scores,
    _load_llm_judgments,
    _resolve_llm_judge,
    _resolve_skill_paths,
    _write_evaluation_outputs,
    load_config,
    main,
)
from skillprism.llm_judge import MultiJudgeResult


def _make_skill(tmp_path: Path, name: str = "test-skill") -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: A test skill.\n---\n\n# Test Skill\n\n## Quick Start\n\n```python\nprint('hi')\n```\n",
        encoding="utf-8",
    )
    return skill_dir


def test_build_parser_requires_skill_or_all() -> None:
    parser = _build_evaluate_parser()
    args = parser.parse_args(["skills/foo"])
    assert args.skill == "skills/foo"
    assert args.all is False


def test_resolve_skill_paths_single(tmp_path: Path) -> None:
    parser = _build_evaluate_parser()
    args = parser.parse_args([str(tmp_path / "foo")])
    paths = _resolve_skill_paths(args, tmp_path)
    assert paths == [tmp_path / "foo"]


def test_resolve_skill_paths_all(tmp_path: Path) -> None:
    (tmp_path / "foo").mkdir()
    (tmp_path / "bar").mkdir()
    parser = _build_evaluate_parser()
    args = parser.parse_args(["--all", "--skills-dir", str(tmp_path)])
    paths = _resolve_skill_paths(args, tmp_path)
    assert paths == [tmp_path / "bar", tmp_path / "foo"]


def test_load_llm_judgments_valid(tmp_path: Path) -> None:
    path = tmp_path / "judgments.json"
    path.write_text(
        '{"judges": [{"dimension": "D2", "scores": [4], "reasons": ["ok"], "aggregated_score": 4, "aggregate": "median"}]}',
        encoding="utf-8",
    )
    judgments = _load_llm_judgments(str(path))
    assert judgments is not None
    assert isinstance(judgments["D2"], MultiJudgeResult)


def test_load_llm_judgments_missing() -> None:
    assert _load_llm_judgments(None) is None


def test_load_llm_judgments_invalid(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    assert _load_llm_judgments(str(path)) is None


def test_resolve_llm_judge_without_flag() -> None:
    parser = _build_evaluate_parser()
    args = parser.parse_args(["skills/foo"])
    assert _resolve_llm_judge(args, {}) is None


def test_write_evaluation_outputs_single(tmp_path: Path, capsys) -> None:
    skill_dir = _make_skill(tmp_path)
    from skillprism.evaluate_skill_rubric import SkillReport

    dims = [DimensionResult(code=f"D{i}", name=f"Dimension {i}", score=3) for i in range(1, 10)]
    sr = SkillReport(name="test-skill", path=skill_dir, skill_type="generic", dimensions=dims)

    parser = _build_evaluate_parser()
    args = parser.parse_args([str(skill_dir), "--detailed"])
    _write_evaluation_outputs([sr], args, tmp_path, load_config(DEFAULT_CONFIG))
    captured = capsys.readouterr()
    assert "test-skill" in captured.out or "C" in captured.out


def test_load_baseline_scores(tmp_path: Path) -> None:
    md = "# Skill Scorecard\n\n| Skill | Score |\n|---|---|\n| foo | 75.0 |\n"
    path = tmp_path / "baseline.md"
    path.write_text(md, encoding="utf-8")
    scores = _load_baseline_scores(path)
    assert scores.get("foo") == 75.0


def _score_to_dims(score: float) -> list[DimensionResult]:
    """Return nine D1-D9 DimensionResults that total approximately ``score``.

    ``score`` is the total weighted score (0-100).  All dimensions use the
    default weight of 0.1 except D2 at 0.15, which is enough to nudge totals
    by ~3 points per level.
    """
    base = int(round(score / 20))
    extra = 0 if score < 60 else 1
    return [
        DimensionResult(code="D1", name="D1", score=max(1, min(5, base))),
        DimensionResult(code="D2", name="D2", score=max(1, min(5, base + extra))),
        DimensionResult(code="D3", name="D3", score=max(1, min(5, base))),
        DimensionResult(code="D4", name="D4", score=max(1, min(5, base))),
        DimensionResult(code="D5", name="D5", score=max(1, min(5, base))),
        DimensionResult(code="D6", name="D6", score=max(1, min(5, base))),
        DimensionResult(code="D7", name="D7", score=max(1, min(5, base))),
        DimensionResult(code="D8", name="D8", score=max(1, min(5, base))),
        DimensionResult(code="D9", name="D9", score=max(1, min(5, base))),
    ]


def test_check_ratchet_no_regression(tmp_path: Path) -> None:
    from skillprism.evaluate_skill_rubric import SkillReport

    dims = _score_to_dims(60.0)
    sr = SkillReport(name="foo", path=tmp_path / "foo", skill_type="generic", dimensions=dims)
    md = "# Skill Scorecard\n\n| Skill | Score |\n|---|---|\n| foo | 50.0 |\n"
    baseline = tmp_path / "baseline.md"
    baseline.write_text(md, encoding="utf-8")
    parser = _build_evaluate_parser()
    args = parser.parse_args(["--ratchet", "--ratchet-baseline", str(baseline)])
    assert _check_ratchet([sr], args, tmp_path, load_config(DEFAULT_CONFIG)) == 0


def test_check_ratchet_regression(tmp_path: Path) -> None:
    from skillprism.evaluate_skill_rubric import SkillReport

    dims = _score_to_dims(40.0)
    sr = SkillReport(name="foo", path=tmp_path / "foo", skill_type="generic", dimensions=dims)
    md = "# Skill Scorecard\n\n| Skill | Score |\n|---|---|\n| foo | 80.0 |\n"
    baseline = tmp_path / "baseline.md"
    baseline.write_text(md, encoding="utf-8")
    parser = _build_evaluate_parser()
    args = parser.parse_args(["--ratchet", "--ratchet-baseline", str(baseline)])
    assert _check_ratchet([sr], args, tmp_path, load_config(DEFAULT_CONFIG)) == 1


def test_main_single_skill(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    with patch("sys.argv", ["evaluate-skill", str(skill_dir)]):
        assert main() == 0


def test_main_all_skills(tmp_path: Path) -> None:
    _make_skill(tmp_path, "foo")
    _make_skill(tmp_path, "bar")
    out = tmp_path / "scorecard.md"
    with patch(
        "sys.argv",
        [
            "evaluate-skill",
            "--all",
            "--skills-dir",
            str(tmp_path),
            "--output",
            str(out),
        ],
    ):
        assert main() == 0
    assert out.exists()


def test_main_with_llm_judgments(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    judgments = tmp_path / "judgments.json"
    judgments.write_text(
        '{"judges": [{"dimension": "D2", "scores": [5], "reasons": ["ok"], "aggregated_score": 5, "aggregate": "median"}]}',
        encoding="utf-8",
    )
    with patch(
        "sys.argv",
        [
            "evaluate-skill",
            str(skill_dir),
            "--llm-judgments",
            str(judgments),
        ],
    ):
        assert main() == 0


def test_main_no_args_prints_help(capsys) -> None:
    with patch("sys.argv", ["evaluate-skill"]):
        assert main() == 2
    captured = capsys.readouterr()
    assert "usage" in captured.out
