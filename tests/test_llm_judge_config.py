#!/usr/bin/env python3
"""Tests for configurable LLM judge prompts and reproducibility metadata."""

from __future__ import annotations

from skillprism.llm_judge import (
    LLMJudge,
    _build_prompt,
    judge_dimension_multi,
)


def test_default_prompt_uses_built_in() -> None:
    judge = LLMJudge(command=["echo"], model="test-model", temperature=0.5, prompt_version="v1")
    prompt = _build_prompt("D2", "# Skill", 3, judge)
    assert "documentation clarity and completeness" in prompt
    assert "test-model" not in prompt  # model is metadata, not part of prompt


def test_custom_prompt_template() -> None:
    judge = LLMJudge(
        command=["echo"],
        prompts={
            "D2": "Custom prompt for {dimension}: focus={focus}, score={engine_score}.\n{content}"
        },
    )
    prompt = _build_prompt("D2", "# Skill", 4, judge)
    assert "Custom prompt for D2" in prompt
    assert "focus=documentation clarity" in prompt
    assert "score=4" in prompt


def test_custom_system_prompt_not_in_user_prompt() -> None:
    judge = LLMJudge(command=["echo"], system_prompt="Custom system prompt")
    prompt = _build_prompt("D2", "# Skill", 3, judge)
    assert "Custom system prompt" not in prompt


def test_from_config_reads_reproducibility_fields() -> None:
    config = {
        "llm_judge": {
            "enabled": True,
            "command": "python judge.py",
            "model": "moonshot-v1-8k",
            "temperature": 0.3,
            "prompt_version": "2.0",
            "system_prompt": "You are a reviewer.",
            "prompts": {"D2": "D2 template {dimension} {focus} {engine_score} {content}"},
        }
    }
    judge = LLMJudge.from_config(config)
    assert judge is not None
    assert judge.model == "moonshot-v1-8k"
    assert judge.temperature == 0.3
    assert judge.prompt_version == "2.0"
    assert judge.system_prompt == "You are a reviewer."
    assert judge.prompts["D2"] == "D2 template {dimension} {focus} {engine_score} {content}"


def test_from_env_reads_model_and_temperature() -> None:
    import os

    old_cmd = os.environ.get("SKILLPRISM_LLM_JUDGE_COMMAND")
    old_model = os.environ.get("SKILLPRISM_LLM_JUDGE_MODEL")
    old_temp = os.environ.get("SKILLPRISM_LLM_JUDGE_TEMPERATURE")
    try:
        os.environ["SKILLPRISM_LLM_JUDGE_COMMAND"] = "python judge.py"
        os.environ["SKILLPRISM_LLM_JUDGE_MODEL"] = "gpt-4"
        os.environ["SKILLPRISM_LLM_JUDGE_TEMPERATURE"] = "0.7"
        judge = LLMJudge.from_env()
        assert judge is not None
        assert judge.model == "gpt-4"
        assert judge.temperature == 0.7
    finally:
        if old_cmd is None:
            os.environ.pop("SKILLPRISM_LLM_JUDGE_COMMAND", None)
        else:
            os.environ["SKILLPRISM_LLM_JUDGE_COMMAND"] = old_cmd
        if old_model is None:
            os.environ.pop("SKILLPRISM_LLM_JUDGE_MODEL", None)
        else:
            os.environ["SKILLPRISM_LLM_JUDGE_MODEL"] = old_model
        if old_temp is None:
            os.environ.pop("SKILLPRISM_LLM_JUDGE_TEMPERATURE", None)
        else:
            os.environ["SKILLPRISM_LLM_JUDGE_TEMPERATURE"] = old_temp


def test_multi_judge_result_metadata() -> None:
    judge = LLMJudge(
        command=["echo"],
        model="model-x",
        temperature=0.1,
        prompt_version="3.0",
        n_judges=1,
    )

    def fake_call(prompt: str) -> str:
        return '{"score": 4, "reason": "ok"}'

    judge.caller = fake_call
    result = judge_dimension_multi(judge, "D2", "# Skill", 3)
    assert result is not None
    assert result.model == "model-x"
    assert result.temperature == 0.1
    assert result.prompt_version == "3.0"
    d = result.to_dict()
    assert d["model"] == "model-x"
    assert d["temperature"] == 0.1
    assert d["prompt_version"] == "3.0"
