#!/usr/bin/env python3
"""P1-2..P1-6: score-fidelity regression tests."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from skillprism.evaluate_skill_rubric import (
    BUILTIN_DIMENSION_EVALUATORS,
    DEFAULT_CONFIG,
    _read_frontmatter,
    _score_from_checks,
    evaluate_skill,
    get_weights,
    load_config,
)
from skillprism.skill_lens_checks import _count_hedge_words

# --------------------------- P1-2: skipped checks --------------------------- #


def test_score_from_checks_excludes_skipped() -> None:
    """Skipped checks must not inflate the score (3 real fails + 3 skips → low)."""
    checks: List[Tuple[bool, str, str]] = [
        (False, "", "fail1"),
        (False, "", "fail2"),
        (False, "", "fail3"),
        (True, "shellcheck not installed; skipped", ""),
        (True, "未安装，跳过", ""),
        (True, "skipped: optional", ""),
    ]
    result = _score_from_checks(checks)
    assert result.skipped_checks == 3
    # 3 real failures out of 3 real checks → ratio 0 → score 1.
    assert result.score == 1


def test_score_from_checks_all_pass_no_skips() -> None:
    checks = [(True, "ok1", ""), (True, "ok2", ""), (True, "ok3", "")]
    result = _score_from_checks(checks)
    assert result.skipped_checks == 0
    assert result.score == 5


# --------------------------- P1-5: CRLF frontmatter ------------------------- #


def test_frontmatter_parses_crlf(tmp_path: Path) -> None:
    """CRLF-encoded SKILL.md frontmatter must be detected (Windows fix)."""
    skill_dir = tmp_path / "crlf_skill"
    skill_dir.mkdir()
    content = "---\r\nname: crlf-test\r\ndescription: A CRLF skill.\r\n---\r\n\r\n# Body\r\n"
    (skill_dir / "SKILL.md").write_bytes(content.encode("utf-8"))
    fm, found = _read_frontmatter(skill_dir)
    assert found is True
    assert fm.get("name") == "crlf-test"


def test_frontmatter_parses_lf(tmp_path: Path) -> None:
    skill_dir = tmp_path / "lf_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: lf-test\ndescription: x.\n---\n\n# Body\n", encoding="utf-8"
    )
    fm, found = _read_frontmatter(skill_dir)
    assert found is True
    assert fm.get("name") == "lf-test"


# --------------------------- P1-6: CJK hedge words -------------------------- #


def test_cjk_hedge_words_detected() -> None:
    """Chinese hedge words must be counted (\\b never matches CJK boundaries)."""
    content = "请视情况而定调整参数，酌情处理，适当增减。"
    assert _count_hedge_words(content) == 3


def test_ascii_hedge_words_still_match() -> None:
    assert _count_hedge_words("I suggest you use judgment here.") == 2


# --------------------------- P1-3: weight normalization -------------------- #


def test_get_weights_normalizes_when_sum_off() -> None:
    config = load_config(DEFAULT_CONFIG)
    # Corrupt the weights to sum > 1.
    config["scoring"]["weights"] = {f"D{i}": 0.2 for i in range(1, 10)}  # 9*0.2 = 1.8
    weights = get_weights(config)
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_total_score_never_exceeds_100_with_default_weights(tmp_path: Path) -> None:
    skill_dir = tmp_path / "weights_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: w\ndescription: x.\n---\n# W\n", encoding="utf-8"
    )
    config = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, config)
    assert report.total_weighted(get_weights(config)) <= 100.0


# --------------------------- P1-4: dimension failure placeholder ----------- #


def test_dimension_evaluator_failure_inserts_placeholder(tmp_path: Path) -> None:
    """A crashing evaluator must not silently drop the max achievable score."""
    skill_dir = tmp_path / "faildim_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: f\ndescription: x.\n---\n# F\n", encoding="utf-8"
    )
    config = load_config(DEFAULT_CONFIG)

    original = BUILTIN_DIMENSION_EVALUATORS["D1"]

    def boom(*args, **kwargs):
        raise RuntimeError("simulated evaluator crash")

    BUILTIN_DIMENSION_EVALUATORS["D1"] = boom
    try:
        report = evaluate_skill(skill_dir, config)
        # The crashed dimension must appear as score=1, not be missing.
        assert any(
            d.score == 1 and d.suggestions and "simulated evaluator crash" in d.suggestions[0]
            for d in report.dimensions
        )
        # All 9 dimensions present → weights stay consistent.
        assert len(report.dimensions) == len(BUILTIN_DIMENSION_EVALUATORS)
        assert "failed" in " ".join(report.errors).lower()
    finally:
        BUILTIN_DIMENSION_EVALUATORS["D1"] = original
