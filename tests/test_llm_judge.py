#!/usr/bin/env python3
"""Unit tests for optional LLM-as-judge."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillprism.llm_judge import LLMJudge, blend_score, judge_dimension


class TestLLMJudge:
    def test_mock_caller(self) -> None:
        def caller(prompt: str) -> str:
            return json.dumps({"score": 4, "reason": "Clear and well structured."})

        judge = LLMJudge(caller=caller, weight=0.3)
        result = judge.judge("Rate this doc.")
        assert result is not None
        assert result.score == 4
        assert "well structured" in result.reason

    def test_parse_markdown_json(self) -> None:
        def caller(prompt: str) -> str:
            return '```json\n{"score": 5, "reason": "Great"}\n```'

        judge = LLMJudge(caller=caller)
        result = judge.judge("x")
        assert result is not None
        assert result.score == 5

    def test_parse_json_with_preamble_and_postamble(self) -> None:
        """JSON embedded in prose must be recovered via the regex fallback."""

        def caller(prompt: str) -> str:
            return (
                'Here is my judgment:\n```json\n{"score": 4, "reason": "Clear."}\n```\n'
                "Hope that helps."
            )

        judge = LLMJudge(caller=caller)
        result = judge.judge("x")
        assert result is not None
        assert result.score == 4

    def test_parse_bare_json_in_prose(self) -> None:
        def caller(prompt: str) -> str:
            return 'Sure: {"score": 3, "reason": "Average"} — done.'

        judge = LLMJudge(caller=caller)
        result = judge.judge("x")
        assert result is not None
        assert result.score == 3

    def test_unavailable_returns_none_on_judge_dimension(self) -> None:
        judge = LLMJudge()
        assert judge_dimension(judge, "D2", "content", 3) is None

    def test_blend_score(self) -> None:
        assert blend_score(2, 4, 0.5) == 3
        assert blend_score(2, 4, 0.0) == 2
        assert blend_score(2, 4, 1.0) == 4

    def test_score_clamping(self) -> None:
        def caller(prompt: str) -> str:
            return json.dumps({"score": 10, "reason": "Overflow"})

        judge = LLMJudge(caller=caller)
        result = judge.judge("x")
        assert result is not None
        assert result.score == 5

    def test_invalid_json_returns_none(self) -> None:
        def caller(prompt: str) -> str:
            return "not json"

        judge = LLMJudge(caller=caller)
        assert judge.judge("x") is None

    def test_missing_reason_rejected_when_required(self) -> None:
        def caller(prompt: str) -> str:
            return json.dumps({"score": 4})

        judge = LLMJudge(caller=caller, require_reason=True)
        assert judge.judge("x") is None

    def test_missing_reason_accepted_when_not_required(self) -> None:
        def caller(prompt: str) -> str:
            return json.dumps({"score": 4})

        judge = LLMJudge(caller=caller, require_reason=False)
        result = judge.judge("x")
        assert result is not None
        assert result.score == 4

    def test_retries_eventually_succeed(self) -> None:
        calls = []

        def caller(prompt: str) -> str:
            calls.append(prompt)
            if len(calls) < 2:
                return "bad json"
            return json.dumps({"score": 3, "reason": "Okay."})

        judge = LLMJudge(caller=caller, max_retries=2)
        result = judge.judge("x")
        assert result is not None
        assert result.score == 3
        assert len(calls) == 2

    def test_retries_exhausted_returns_none(self) -> None:
        def caller(prompt: str) -> str:
            return "bad json"

        judge = LLMJudge(caller=caller, max_retries=1)
        assert judge.judge("x") is None

    def test_outlier_score_ignored(self) -> None:
        def caller(prompt: str) -> str:
            return json.dumps({"score": 5, "reason": "Great"})

        judge = LLMJudge(caller=caller, outlier_threshold=2)
        # Engine score 2, LLM 5 -> distance 3 > threshold -> ignored
        assert judge_dimension(judge, "D2", "content", 2) is None

    def test_non_outlier_score_accepted(self) -> None:
        def caller(prompt: str) -> str:
            return json.dumps({"score": 4, "reason": "Good"})

        judge = LLMJudge(caller=caller, outlier_threshold=2)
        result = judge_dimension(judge, "D2", "content", 2)
        assert result is not None
        assert result.score == 4

    def test_from_config(self) -> None:
        config = {
            "llm_judge": {
                "enabled": True,
                "command": "python scripts/judge.py",
                "weight": 0.4,
                "max_retries": 3,
                "outlier_threshold": 1,
                "require_reason": False,
            }
        }
        judge = LLMJudge.from_config(config)
        assert judge is not None
        assert judge.command == ["python", "scripts/judge.py"]
        assert judge.weight == 0.4
        assert judge.max_retries == 3
        assert judge.outlier_threshold == 1
        assert judge.require_reason is False

    def test_from_config_disabled(self) -> None:
        assert LLMJudge.from_config({}) is None
        assert LLMJudge.from_config({"llm_judge": {"enabled": False}}) is None

    def test_judge_dimension_integration(self) -> None:
        def caller(prompt: str) -> str:
            return json.dumps({"score": 3, "reason": "Adequate."})

        judge = LLMJudge(caller=caller, weight=0.5)
        result = judge_dimension(judge, "D2", "# Title\n", 2)
        assert result is not None
        assert result.score == 3
        assert "Adequate" in result.reason
