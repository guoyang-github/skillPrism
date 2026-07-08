"""Tests for skillprism.prompts_verification."""

from __future__ import annotations

from skillprism.prompts_verification import (
    PromptsVerificationReport,
    PromptVerificationResult,
    format_prompts_verification_report,
    load_prompts_verification,
    save_prompts_verification,
)


def test_prompt_result_to_dict() -> None:
    r = PromptVerificationResult(
        prompt_id="p1",
        prompt="hello",
        without_skill_output="a",
        with_skill_output="b",
        expected="b",
        improvement_score=0.5,
        passed=True,
        eval_mode="full_test",
    )
    d = r.to_dict()
    assert d["prompt_id"] == "p1"
    assert d["passed"] is True
    assert d["eval_mode"] == "full_test"


def test_report_properties() -> None:
    report = PromptsVerificationReport(skill="s1")
    assert report.all_pass is True
    assert report.pass_rate == 0.0
    assert report.dry_run_ratio == 0.0
    assert report.dry_run_warning is False

    report.results = [
        PromptVerificationResult(
            prompt_id="p1",
            prompt="x",
            without_skill_output="a",
            with_skill_output="b",
            expected="b",
            passed=True,
            eval_mode="full_test",
        ),
        PromptVerificationResult(
            prompt_id="p2",
            prompt="y",
            without_skill_output="a",
            with_skill_output="c",
            expected="b",
            passed=False,
            eval_mode="dry_run",
        ),
    ]
    assert report.all_pass is False
    assert report.pass_rate == 0.5
    assert report.dry_run_ratio == 0.5
    assert report.dry_run_warning is True


def test_to_dict_summary(tmp_path) -> None:
    report = PromptsVerificationReport(
        skill="s1",
        results=[
            PromptVerificationResult(
                prompt_id="p1",
                prompt="x",
                without_skill_output="a",
                with_skill_output="b",
                expected="b",
                passed=True,
            )
        ],
        summary={"foo": "bar"},
    )
    d = report.to_dict()
    assert d["skill"] == "s1"
    assert d["summary"]["total"] == 1
    assert d["summary"]["passed"] == 1
    assert d["summary"]["foo"] == "bar"


def test_save_and_load(tmp_path) -> None:
    report = PromptsVerificationReport(
        skill="s1",
        results=[
            PromptVerificationResult(
                prompt_id="p1",
                prompt="x",
                without_skill_output="a",
                with_skill_output="b",
                expected="b",
                passed=True,
            )
        ],
    )
    path = tmp_path / "report.json"
    save_prompts_verification(path, report)
    loaded = load_prompts_verification(path)
    assert loaded is not None
    assert loaded.skill == "s1"
    assert loaded.all_pass is True


def test_load_missing_returns_none(tmp_path) -> None:
    assert load_prompts_verification(tmp_path / "nope.json") is None


def test_load_invalid_returns_none(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    assert load_prompts_verification(path) is None


def test_format_report_empty() -> None:
    report = PromptsVerificationReport(skill="s1")
    text = format_prompts_verification_report(report)
    assert "No prompts verified" in text


def test_format_report_with_warning() -> None:
    report = PromptsVerificationReport(
        skill="s1",
        results=[
            PromptVerificationResult(
                prompt_id="p1",
                prompt="x",
                without_skill_output="a",
                with_skill_output="b",
                expected="b",
                passed=True,
                eval_mode="dry_run",
            ),
            PromptVerificationResult(
                prompt_id="p2",
                prompt="y",
                without_skill_output="a",
                with_skill_output="c",
                expected="b",
                passed=False,
                eval_mode="dry_run",
            ),
        ],
    )
    text = format_prompts_verification_report(report)
    assert "PASS" in text
    assert "FAIL" in text
    assert "dry-run ratio" in text
    assert "Warning" in text
