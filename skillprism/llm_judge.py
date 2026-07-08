#!/usr/bin/env python3
"""Optional LLM-as-judge for subjective rubric dimensions.

This module is intentionally provider-agnostic. The engine does not depend on
any LLM library. Users provide a caller (subprocess command or callable) that
accepts a prompt and returns a JSON judgment.

Example caller (subprocess):
    export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"
    evaluate-skill skills/foo --llm-judge

Example JSON output expected from the caller:
    {"score": 4, "reason": "Documentation is clear and includes examples."}
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, cast


@dataclass
class LLMJudgeResult:
    score: int  # 1-5
    reason: str


DEFAULT_SYSTEM_PROMPT = (
    "You are an expert reviewer evaluating an AI agent SKILL.md file. "
    "Respond with ONLY a JSON object containing exactly two keys: "
    '"score" (integer 1-5) and "reason" (concise explanation). '
    "Do not add markdown fences or explanations outside the JSON."
)

DEFAULT_PROMPTS: Dict[str, str] = {
    "D2": (
        "Evaluate the following SKILL.md for dimension {dimension} (documentation clarity and "
        "completeness: structure, examples, input/output descriptions, tables, version "
        "notes, and pitfalls/troubleshooting). The rule-based engine gave it a score of "
        "{engine_score}/5."
    ),
    "D5": (
        "Evaluate the following SKILL.md for dimension {dimension} (domain accuracy: whether "
        "references/citations, parameters, recommended practices, and caution notes are "
        "present and plausible for the skill's domain). The rule-based engine gave it a "
        "score of {engine_score}/5."
    ),
    "D6": (
        "Evaluate the following SKILL.md for dimension {dimension} (LLM callability: description "
        "quality, keywords, when-to-use guidance, and tool selection clarity). The "
        "rule-based engine gave it a score of {engine_score}/5."
    ),
    "D8": (
        "Evaluate the following SKILL.md for dimension {dimension} (maintainability: versioning, "
        "organization, and update practices). The rule-based engine gave it a score of "
        "{engine_score}/5."
    ),
}


@dataclass
class MultiJudgeResult:
    """Aggregated result from multiple independent judges."""

    dimension: str
    scores: List[int] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    aggregated_score: int = 0
    aggregate: str = "median"
    model: str = "unknown"
    temperature: float = 0.0
    prompt_version: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "scores": self.scores,
            "reasons": self.reasons,
            "aggregated_score": self.aggregated_score,
            "aggregate": self.aggregate,
            "model": self.model,
            "temperature": self.temperature,
            "prompt_version": self.prompt_version,
        }


class LLMJudge:
    """LLM-based second opinion for subjective rubric dimensions (D2, D5).

    The judge is defensive by default:
      - JSON schema is validated (score + reason).
      - Score is clamped to the rubric range [1, 5].
      - Calls are retried on parse/schema failures.
      - Outlier scores that deviate too far from the engine score are ignored.
      - Supports multiple independent judges with configurable aggregation.
    """

    def __init__(
        self,
        caller: Optional[Callable[[str], str]] = None,
        command: Optional[List[str]] = None,
        weight: float = 0.3,
        max_retries: int = 2,
        outlier_threshold: int = 2,
        require_reason: bool = True,
        n_judges: int = 2,
        aggregate: str = "median",
        model: str = "unknown",
        temperature: float = 0.2,
        prompt_version: str = "default",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        prompts: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Args:
            caller: Optional callable(prompt_text) -> response_text.
            command: Optional subprocess command to call as ["cmd", "arg", ...].
                     The prompt is passed via stdin.
            weight: How much to blend the LLM score into the engine score (0-1).
            max_retries: Number of extra attempts after the first failed parse.
            outlier_threshold: Ignore LLM scores whose absolute distance from the
                engine score exceeds this value.
            require_reason: If True, reject judgments with an empty reason string.
            n_judges: Number of independent judges to call. Each call is independent
                (fresh judge) when n_judges > 1.
            aggregate: How to aggregate multiple scores: "median", "mean", "min", "max".
            model: Model identifier used by the judge (for reproducibility metadata).
            temperature: Sampling temperature used by the judge.
            prompt_version: Version tag for the prompt template.
            system_prompt: System prompt sent to the judge.
            prompts: Per-dimension user prompt templates keyed by dimension code.
        """
        self.caller = caller
        self.command = command
        self.weight = weight
        self.max_retries = max(0, max_retries)
        self.outlier_threshold = max(0, outlier_threshold)
        self.require_reason = require_reason
        self.n_judges = max(1, n_judges)
        self.aggregate = aggregate
        self.model = model
        self.temperature = temperature
        self.prompt_version = prompt_version
        self.system_prompt = system_prompt
        self.prompts = prompts or DEFAULT_PROMPTS.copy()

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> Optional["LLMJudge"]:
        """Build an LLMJudge from the `llm_judge` section of skill_rubric_types.yaml."""
        cfg = config.get("llm_judge")
        if not cfg or not cfg.get("enabled"):
            return None
        command = cfg.get("command")
        if isinstance(command, str):
            command = command.split()
        prompts = cfg.get("prompts")
        return cls(
            command=command,
            weight=float(cfg.get("weight", 0.3)),
            max_retries=int(cfg.get("max_retries", 2)),
            outlier_threshold=int(cfg.get("outlier_threshold", 2)),
            require_reason=bool(cfg.get("require_reason", True)),
            n_judges=int(cfg.get("n_judges", 1)),
            aggregate=str(cfg.get("aggregate", "median")),
            model=str(cfg.get("model", "unknown")),
            temperature=float(cfg.get("temperature", 0.2)),
            prompt_version=str(cfg.get("prompt_version", "default")),
            system_prompt=str(cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT)),
            prompts=cast(Optional[Dict[str, str]], prompts) if prompts else None,
        )

    @classmethod
    def from_env(cls) -> Optional["LLMJudge"]:
        """Build an LLMJudge from SKILLPRISM_LLM_JUDGE_COMMAND env var."""
        cmd = os.environ.get("SKILLPRISM_LLM_JUDGE_COMMAND")
        if not cmd:
            return None
        return cls(
            command=cmd.split(),
            model=os.environ.get("SKILLPRISM_LLM_JUDGE_MODEL", "unknown"),
            temperature=float(os.environ.get("SKILLPRISM_LLM_JUDGE_TEMPERATURE", "0.2")),
        )

    def is_available(self) -> bool:
        return self.caller is not None or self.command is not None

    def _call_subprocess(self, prompt: str) -> str:
        if not self.command:
            raise RuntimeError("No LLM judge command configured")
        executable = shutil.which(self.command[0])
        if executable is None:
            raise RuntimeError(f"LLM judge command not found: {self.command[0]}")
        cmd = [executable] + self.command[1:]
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"LLM judge failed: {proc.stderr[:500]}")
        return proc.stdout

    def _call(self, prompt: str) -> str:
        if self.caller:
            return self.caller(prompt)
        return self._call_subprocess(prompt)

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """Extract the JSON object from a judge response.

        Handles: bare JSON, a single ```json ... ``` fence pair, and JSON
        embedded in prose (preamble/postamble). Previously a naive
        ``strip("`")`` stripped *all* leading/trailing backticks and could not
        recover JSON from a fenced block wrapped in prose.
        """
        import re

        cleaned = text.strip()
        # Strip one leading/trailing code fence pair only.
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE)
        if fence:
            return fence.group(1).strip()
        # Bare JSON object.
        if cleaned.startswith("{") and cleaned.endswith("}"):
            return cleaned
        # Fallback: first {...} object anywhere in the text (preamble/postamble).
        match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
        if match:
            return match.group(0)
        return cleaned

    def _validate(self, data: Any) -> Optional[LLMJudgeResult]:
        """Validate parsed judgment and return a result, or None if invalid."""
        if not isinstance(data, dict):
            return None
        if "score" not in data:
            return None
        try:
            score = int(float(data["score"]))
        except (ValueError, TypeError):
            return None
        score = max(1, min(5, score))

        reason = str(data.get("reason", "")).strip()
        if self.require_reason and not reason:
            return None
        return LLMJudgeResult(score=score, reason=reason or "No reason provided.")

    def _parse(self, text: str) -> Optional[LLMJudgeResult]:
        """Parse JSON judgment from response text with schema validation."""
        cleaned = self._extract_json_block(text)
        data = json.loads(cleaned)
        return self._validate(data)

    def judge(self, prompt: str) -> Optional[LLMJudgeResult]:
        """Call the judge and return a validated result, or None on failure.

        Retries up to ``max_retries`` times if parsing or schema validation fails.
        On retry, a corrective instruction is appended so the model is told to
        emit *only* a JSON object — previously the identical prompt was re-sent,
        which commonly reproduced the same failure mode.
        """
        _last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                call_prompt = prompt
                if attempt > 0:
                    call_prompt = (
                        prompt + "\n\nNOTE: Your previous response was not valid JSON. "
                        'Respond with ONLY a JSON object {"score": int, "reason": str}, '
                        "no markdown fences, no prose."
                    )
                response = self._call(call_prompt)
                result = self._parse(response)
                if result is not None:
                    return result
                _last_error = "schema validation failed"
            except Exception as exc:
                _last_error = str(exc)
        # All retries exhausted; ignore this judgment.
        if _last_error:
            print(f"Warning: LLM judge failed after {self.max_retries + 1} attempts: {_last_error}")
        return None


def _dimension_focus(code: str) -> str:
    """Return the default focus text for a dimension code."""
    focus_map = {
        "D2": "documentation clarity and completeness: structure, examples, "
        "input/output descriptions, tables, version notes, and pitfalls/troubleshooting",
        "D5": "domain accuracy: whether references/citations, parameters, recommended "
        "practices, and caution notes are present and plausible for the skill's domain",
        "D6": "LLM callability: description quality, keywords, when-to-use guidance, "
        "and tool selection clarity",
        "D8": "maintainability: versioning, organization, and update practices",
    }
    return focus_map.get(code, "overall quality")


def _build_prompt(code: str, content: str, engine_score: int, judge: LLMJudge) -> str:
    """Build the user prompt for a single judge call.

    Uses per-dimension templates from the judge configuration when available,
    falling back to the built-in defaults.
    """
    template = judge.prompts.get(
        code, DEFAULT_PROMPTS.get(code, "Evaluate SKILL.md for dimension {dimension} ({focus}).")
    )
    focus = _dimension_focus(code)
    user_prompt = template.format(
        dimension=code,
        focus=focus,
        engine_score=engine_score,
        content=content[:8000],
    )
    return (
        "You are an expert reviewer evaluating a SKILL.md file for an AI agent skill.\n\n"
        f"{user_prompt}\n\n"
        "Return a JSON object with exactly two keys:\n"
        '  "score": an integer from 1 to 5,\n'
        '  "reason": a concise explanation (one sentence).\n\n'
        f"SKILL.md content:\n---\n{content[:8000]}\n---\n"
    )


def _aggregate_scores(scores: List[int], method: str) -> int:
    """Aggregate multiple judge scores into a single integer score."""
    if not scores:
        return 0
    if method == "min":
        return min(scores)
    if method == "max":
        return max(scores)
    if method == "mean":
        return max(1, min(5, round(sum(scores) / len(scores))))
    # Default: median
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    mid = n // 2
    if n % 2 == 1:
        return sorted_scores[mid]
    return max(1, min(5, round((sorted_scores[mid - 1] + sorted_scores[mid]) / 2)))


def judge_dimension(
    judge: LLMJudge,
    code: str,
    content: str,
    engine_score: int,
) -> Optional[LLMJudgeResult]:
    """Get LLM second opinion for a single dimension.

    Returns None if the judge is unavailable, fails repeatedly, or returns an
    outlier score that deviates beyond ``judge.outlier_threshold`` from the
    engine score.
    """
    if not judge.is_available():
        return None
    prompt = _build_prompt(code, content, engine_score, judge)
    result = judge.judge(prompt)
    if result is None:
        return None
    if abs(result.score - engine_score) > judge.outlier_threshold:
        # Log the dropped outlier so disagreement (the most informative case) is
        # not silently discarded — previously these vanished without a trace.
        print(
            f"Warning: LLM judge {code} score {result.score} dropped as outlier "
            f"(engine={engine_score}, threshold={judge.outlier_threshold}). "
            f"Reason: {result.reason[:120]}"
        )
        return None
    return result


def judge_dimension_multi(
    judge: LLMJudge,
    code: str,
    content: str,
    engine_score: int,
) -> Optional[MultiJudgeResult]:
    """Get multiple independent LLM opinions for a single dimension and aggregate them.

    Returns None if the judge is unavailable or all calls fail.
    """
    if not judge.is_available():
        return None

    prompt = _build_prompt(code, content, engine_score, judge)
    results: List[LLMJudgeResult] = []
    for _ in range(judge.n_judges):
        result = judge.judge(prompt)
        if result is not None:
            # Outlier filtering per individual judge result
            if abs(result.score - engine_score) <= judge.outlier_threshold:
                results.append(result)
            else:
                print(
                    f"Warning: LLM multi-judge {code} score {result.score} dropped as "
                    f"outlier (engine={engine_score}, threshold={judge.outlier_threshold}). "
                    f"Reason: {result.reason[:120]}"
                )

    if not results:
        return None

    scores = [r.score for r in results]
    reasons = [r.reason for r in results]
    aggregated = _aggregate_scores(scores, judge.aggregate)
    return MultiJudgeResult(
        dimension=code,
        scores=scores,
        reasons=reasons,
        aggregated_score=aggregated,
        aggregate=judge.aggregate,
        model=judge.model,
        temperature=judge.temperature,
        prompt_version=judge.prompt_version,
    )


def blend_score(engine_score: int, llm_score: int, weight: float) -> int:
    """Blend engine and LLM scores into a single integer score."""
    blended = engine_score * (1 - weight) + llm_score * weight
    return max(1, min(5, round(blended)))
