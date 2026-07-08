#!/usr/bin/env python3
"""CLI and helper tests for skillprism.optimize_skill."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skillprism.evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    DimensionResult,
    SkillReport,
    load_config,
)
from skillprism.optimize_skill import (
    _find_skill_code,
    _format_benchmark_summary,
    benchmark_acceptable,
    benchmark_improved,
    build_suggestion,
    display_score,
    find_weakest_dimension,
    judge_result_to_dict,
    load_skill_md,
    main,
    render_diff,
    run_skill_benchmark,
    save_skill_md,
    select_weakest_dimension,
)


def _make_skill(tmp_path: Path, name: str = "test-skill") -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: A test skill.\n---\n\n# Test Skill\n",
        encoding="utf-8",
    )
    return skill_dir


def test_load_and_save_skill_md(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    text = load_skill_md(skill_dir)
    assert "# Test Skill" in text
    save_skill_md(skill_dir, "---\nname: x\n---\n\n# X\n")
    assert "# X" in load_skill_md(skill_dir)


def test_load_skill_md_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_skill_md(tmp_path)


def test_find_skill_code(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    assert _find_skill_code(skill_dir) is None

    code = skill_dir / "examples" / "minimal_example.py"
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_text("print('hi')", encoding="utf-8")
    assert _find_skill_code(skill_dir) == code

    explicit = tmp_path / "other.py"
    explicit.write_text("x", encoding="utf-8")
    assert _find_skill_code(skill_dir, explicit) == explicit


def test_run_skill_benchmark_no_skill_type(tmp_path: Path) -> None:
    assert run_skill_benchmark(tmp_path, None, tmp_path / "registry.yaml", tmp_path) is None


def test_run_skill_benchmark_success(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    out_dir = tmp_path / "out"
    registry = tmp_path / "registry.yaml"
    with patch("skillprism.optimize_skill.run_benchmarks") as mock_run:
        mock_run.return_value = {"_all_pass": True}
        result = run_skill_benchmark(skill_dir, "generic", registry, out_dir)
    assert result == {"_all_pass": True}
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] == "generic"
    assert mock_run.call_args.args[1] == registry


def test_format_benchmark_summary() -> None:
    assert "No benchmark run" in _format_benchmark_summary(None)
    results = {
        "_all_pass": False,
        "benchmarks": {
            "b1": {"_all_pass": True},
            "b2": {"_all_pass": False, "error": "boom"},
        },
    }
    summary = _format_benchmark_summary(results)
    assert "b1: PASS" in summary
    assert "b2: FAIL" in summary
    assert "boom" in summary


def test_benchmark_acceptable() -> None:
    assert benchmark_acceptable(None, None) == (True, "no benchmark data")
    old = {"benchmarks": {"b1": {"_all_pass": True}}}
    new = {"benchmarks": {"b1": {"_all_pass": True}}}
    assert benchmark_acceptable(old, new) == (True, "benchmark acceptable")

    new2 = {"benchmarks": {}}
    assert benchmark_acceptable(old, new2) == (False, "benchmark b1 missing")

    new3 = {"benchmarks": {"b1": {"_all_pass": False}}}
    assert benchmark_acceptable(old, new3) == (False, "benchmark b1 regressed from PASS to FAIL")


def test_benchmark_improved() -> None:
    assert benchmark_improved(None, None) is False
    old = {"benchmarks": {"b1": {"_all_pass": False}}}
    new = {"benchmarks": {"b1": {"_all_pass": True}}}
    assert benchmark_improved(old, new) is True


def test_display_score(tmp_path: Path) -> None:
    dims = [DimensionResult(code=f"D{i}", name=f"D{i}", score=3) for i in range(1, 10)]
    report = SkillReport(name="x", path=tmp_path, skill_type="generic", dimensions=dims)
    config = load_config(DEFAULT_CONFIG)
    score, grade = display_score(report, config)
    assert score == 60.0
    assert grade in {"A", "B", "C", "D", "F"}


def test_find_weakest_dimension() -> None:
    dims = [
        DimensionResult(code="D1", name="D1", score=4),
        DimensionResult(code="D2", name="D2", score=2),
    ]
    report = SkillReport(name="x", path=Path("/tmp/x"), skill_type="generic", dimensions=dims)
    assert find_weakest_dimension(report).code == "D2"
    assert (
        find_weakest_dimension(SkillReport(name="x", path=Path("/tmp/x"), skill_type="generic"))
        is None
    )


def test_select_weakest_dimension_priority(tmp_path: Path) -> None:
    dims = [
        DimensionResult(code="D2", name="D2", score=2),
        DimensionResult(code="D3", name="D3", score=1),
    ]
    report = SkillReport(name="x", path=tmp_path, skill_type="generic", dimensions=dims)
    config = {"optimization": {"priority": {"blockers": ["D2"], "blocker_threshold": 3}}}
    assert select_weakest_dimension(report, config).code == "D2"


def test_build_suggestion(tmp_path: Path) -> None:
    skill_dir = _make_skill(tmp_path)
    dims = [
        DimensionResult(
            code="D2", name="文档可理解性", score=2, evidence=["short"], suggestions=["add"]
        )
    ]
    report = SkillReport(name="test-skill", path=skill_dir, skill_type="generic", dimensions=dims)
    config = load_config(DEFAULT_CONFIG)
    suggestion = build_suggestion(report, config)
    assert "Weakest dimension" in suggestion
    assert "D2" in suggestion


def test_render_diff() -> None:
    base = "a\nb\n"
    current = "a\nc\n"
    diff = render_diff(Path("/tmp/x"), base, current)
    assert "-b" in diff
    assert "+c" in diff


def test_judge_result_to_dict() -> None:
    config = load_config(DEFAULT_CONFIG)
    dims = [DimensionResult(code="D1", name="D1", score=3)]
    report = SkillReport(name="x", path=Path("/tmp/x"), skill_type="generic", dimensions=dims)
    result = MagicMock()
    result.kept = True
    result.applied = True
    result.baseline_score = 50.0
    result.current_score = 60.0
    result.score_delta = 10.0
    result.benchmark_ok = True
    result.benchmark_reason = "ok"
    result.decision_reason = "improved"
    result.diff = ""
    result.dimension_changes = {}
    result.guard_violations = []
    result.current_report = report
    d = judge_result_to_dict(result, config)
    assert d["kept"] is True
    assert d["decision"] == "KEEP"
    assert d["weakest_dimension"]["code"] == "D1"


class TestMain:
    def test_main_missing_skill_dir(self, tmp_path: Path) -> None:
        with patch("sys.argv", ["improve-skill", str(tmp_path / "nope")]):
            assert main() == 2

    def test_main_no_skill_md(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "empty"
        skill_dir.mkdir()
        with patch("sys.argv", ["improve-skill", str(skill_dir)]):
            assert main() == 2

    def test_main_clear_baseline(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path)
        with patch("skillprism.optimize_skill.clear_baseline") as mock_clear:
            with patch("sys.argv", ["improve-skill", str(skill_dir), "--clear-baseline"]):
                assert main() == 0
        mock_clear.assert_called_once_with(skill_dir)

    def test_main_history(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path)
        with patch("skillprism.optimize_skill.load_history", return_value=[]) as mock_load:
            with patch("skillprism.optimize_skill.format_history_table", return_value="history"):
                with patch("sys.argv", ["improve-skill", str(skill_dir), "--history"]):
                    assert main() == 0
        mock_load.assert_called_once_with(skill_dir)

    def test_main_suggest(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path)
        dims = [DimensionResult(code="D1", name="D1", score=3) for _ in range(9)]
        report = SkillReport(
            name="test-skill", path=skill_dir, skill_type="generic", dimensions=dims
        )
        with patch("skillprism.optimize_skill.evaluate_skill", return_value=report):
            with patch("sys.argv", ["improve-skill", str(skill_dir), "--suggest"]):
                assert main() == 0

    def test_main_record_baseline(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path)
        dims = [DimensionResult(code="D1", name="D1", score=3) for _ in range(9)]
        report = SkillReport(
            name="test-skill", path=skill_dir, skill_type="generic", dimensions=dims
        )
        with patch("skillprism.optimize_skill.evaluate_skill", return_value=report):
            with patch("skillprism.optimize_skill.save_baseline") as mock_save:
                with patch("sys.argv", ["improve-skill", str(skill_dir), "--record-baseline"]):
                    assert main() == 0
        mock_save.assert_called_once()

    def test_main_judge_no_baseline(self, tmp_path: Path, capsys) -> None:
        skill_dir = _make_skill(tmp_path)
        with patch("skillprism.optimize_skill.load_baseline", return_value=None):
            with patch("sys.argv", ["improve-skill", str(skill_dir), "--judge"]):
                assert main() == 2
        captured = capsys.readouterr()
        assert "no baseline found" in captured.out

    def _judge_result(self, kept: bool, skill_dir: Path) -> MagicMock:
        result = MagicMock()
        result.kept = kept
        result.applied = True
        result.baseline_score = 50.0
        result.current_score = 60.0
        result.score_delta = 10.0
        result.benchmark_ok = True
        result.benchmark_reason = "ok"
        result.decision_reason = "improved"
        result.diff = ""
        result.dimension_changes = {}
        result.guard_violations = []
        result.current_benchmark = None
        dims = [DimensionResult(code="D1", name="D1", score=3)]
        result.current_report = SkillReport(
            name="x", path=skill_dir, skill_type="generic", dimensions=dims
        )
        return result

    def test_main_judge_kept(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path)
        mock_result = self._judge_result(True, skill_dir)
        with patch("skillprism.optimize_skill.load_baseline", return_value={"score": 50.0}):
            with patch("skillprism.optimize_skill.judge_candidate", return_value=mock_result):
                with patch("sys.argv", ["improve-skill", str(skill_dir), "--judge"]):
                    assert main() == 0

    def test_main_judge_reverted(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path)
        mock_result = self._judge_result(False, skill_dir)
        with patch("skillprism.optimize_skill.load_baseline", return_value={"score": 50.0}):
            with patch("skillprism.optimize_skill.judge_candidate", return_value=mock_result):
                with patch("sys.argv", ["improve-skill", str(skill_dir), "--judge"]):
                    assert main() == 1

    def test_main_judge_output_json(self, tmp_path: Path) -> None:
        skill_dir = _make_skill(tmp_path)
        out_json = tmp_path / "result.json"
        mock_result = self._judge_result(True, skill_dir)
        with patch("skillprism.optimize_skill.load_baseline", return_value={"score": 50.0}):
            with patch("skillprism.optimize_skill.judge_candidate", return_value=mock_result):
                with patch(
                    "sys.argv",
                    ["improve-skill", str(skill_dir), "--judge", "--output-json", str(out_json)],
                ):
                    assert main() == 0
        assert out_json.exists()

    def test_main_auto_edit_no_apply(self, tmp_path: Path, capsys) -> None:
        skill_dir = _make_skill(tmp_path)
        with patch("sys.argv", ["improve-skill", str(skill_dir), "--auto-edit"]):
            assert main() == 1
        captured = capsys.readouterr()
        assert "--apply" in captured.out

    def test_main_auto_edit_missing_editor(self, tmp_path: Path, capsys) -> None:
        skill_dir = _make_skill(tmp_path)
        with patch("skillprism.optimize_skill.SkillEditor") as mock_editor_cls:
            mock_editor_cls.from_config.return_value = None
            mock_editor_cls.from_env.return_value = None
            with patch("sys.argv", ["improve-skill", str(skill_dir), "--auto-edit", "--apply"]):
                assert main() == 2
        captured = capsys.readouterr()
        assert "no editor command" in captured.out

    def test_main_default_hint(self, tmp_path: Path, capsys) -> None:
        skill_dir = _make_skill(tmp_path)
        with patch("sys.argv", ["improve-skill", str(skill_dir)]):
            assert main() == 0
        captured = capsys.readouterr()
        assert "Use one of" in captured.out

    def test_main_llm_judge_unavailable(self, tmp_path: Path, capsys) -> None:
        skill_dir = _make_skill(tmp_path)
        with patch("skillprism.optimize_skill.LLMJudge") as mock_judge_cls:
            mock_judge_cls.from_config.return_value = None
            mock_judge_cls.from_env.return_value = None
            with patch("sys.argv", ["improve-skill", str(skill_dir), "--suggest", "--llm-judge"]):
                assert main() == 0
        captured = capsys.readouterr()
        assert "no LLM judge command configured" in captured.out

    def test_main_invalid_llm_judgments(self, tmp_path: Path, capsys) -> None:
        skill_dir = _make_skill(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        dims = [DimensionResult(code="D1", name="D1", score=3) for _ in range(9)]
        report = SkillReport(
            name="test-skill", path=skill_dir, skill_type="generic", dimensions=dims
        )
        with patch("skillprism.optimize_skill.evaluate_skill", return_value=report):
            with patch(
                "sys.argv",
                [
                    "improve-skill",
                    str(skill_dir),
                    "--suggest",
                    "--llm-judgments",
                    str(bad),
                ],
            ):
                assert main() == 0
        captured = capsys.readouterr()
        assert "failed to load LLM judgments" in captured.out
