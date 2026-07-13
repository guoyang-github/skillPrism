#!/usr/bin/env python3
"""Generate a pre-computed LLM judgments file for skillPrism.

This is useful when:
- You do not want to configure SKILLPRISM_LLM_JUDGE_COMMAND.
- You want the Agent to call LLM judges directly and let the engine consume the results.

Usage:
    export OPENAI_API_KEY=<your-key>
    export OPENAI_BASE_URL=https://api.moonshot.cn/v1
    export OPENAI_MODEL=moonshot-v1-8k

    python scripts/generate_llm_judgments.py skills/my-skill \
        --dimensions D2 D5 \
        --count 2

Output defaults to artifacts/<skill>/llm_judgments.json (override with --output).
The engine auto-discovers that file; to consume it explicitly:

    evaluate-skill skills/my-skill --llm-judgments artifacts/my-skill/llm_judgments.json

Install dependencies:
    pip install openai
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

DIMENSION_PROMPTS: Dict[str, str] = {
    "D2": (
        "Evaluate the following SKILL.md for dimension D2 (documentation clarity and "
        "completeness: structure, examples, input/output descriptions, tables, version "
        "notes, and pitfalls/troubleshooting). The rule-based engine gave it a score of "
        "{engine_score}/5."
    ),
    "D5": (
        "Evaluate the following SKILL.md for dimension D5 (domain accuracy: whether "
        "references/citations, parameters, recommended practices, and caution notes are "
        "present and plausible for the skill's domain). The rule-based engine gave it a "
        "score of {engine_score}/5."
    ),
    "D6": (
        "Evaluate the following SKILL.md for dimension D6 (LLM callability: description "
        "quality, keywords, when-to-use guidance, and tool selection clarity). The "
        "rule-based engine gave it a score of {engine_score}/5."
    ),
    "D8": (
        "Evaluate the following SKILL.md for dimension D8 (maintainability: versioning, "
        "organization, and update practices). The rule-based engine gave it a score of "
        "{engine_score}/5."
    ),
}


def _build_prompt(dimension: str, content: str, engine_score: int) -> str:
    focus = DIMENSION_PROMPTS.get(dimension, "overall quality")
    return (
        f"You are an expert reviewer evaluating a SKILL.md file for an AI agent skill.\n\n"
        f"{focus.format(engine_score=engine_score)}\n\n"
        f"Return a JSON object with exactly two keys:\n"
        f'  "score": an integer from 1 to 5,\n'
        f'  "reason": a concise explanation (one sentence).\n\n'
        f"SKILL.md content:\n---\n{content[:8000]}\n---\n"
    )


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def _call_llm(prompt: str) -> Dict[str, Any]:
    try:
        import openai
    except ImportError as exc:
        print("Error: openai is not installed. Run `pip install openai`.", file=sys.stderr)
        raise SystemExit(1) from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("OPENAI_MODEL")

    if not api_key or not base_url or not model:
        print(
            "Error: OPENAI_API_KEY, OPENAI_BASE_URL and OPENAI_MODEL must be set.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert reviewer evaluating an AI agent SKILL.md file. "
                    "Respond with ONLY a JSON object containing exactly two keys: "
                    '"score" (integer 1-5) and "reason" (concise explanation). '
                    "Do not add markdown fences or explanations outside the JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content or ""
    content = _extract_json(content)
    data = json.loads(content)
    score = max(1, min(5, int(float(data["score"]))))
    reason = str(data.get("reason", "")).strip()
    return {"score": score, "reason": reason}


def _aggregate_scores(scores: List[int], method: str) -> int:
    if not scores:
        return 0
    if method == "min":
        return min(scores)
    if method == "max":
        return max(scores)
    if method == "mean":
        return max(1, min(5, round(sum(scores) / len(scores))))
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    mid = n // 2
    if n % 2 == 1:
        return sorted_scores[mid]
    return max(1, min(5, round((sorted_scores[mid - 1] + sorted_scores[mid]) / 2)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate LLM judgments file for skillPrism.")
    parser.add_argument("skill", help="Path to skill directory")
    parser.add_argument(
        "--dimensions",
        nargs="+",
        default=["D2", "D5"],
        help="Dimensions to judge (default: D2 D5)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=2,
        help="Number of independent judges per dimension (default: 2)",
    )
    parser.add_argument(
        "--aggregate",
        choices=["median", "mean", "min", "max"],
        default="median",
        help="Aggregation method (default: median)",
    )
    parser.add_argument(
        "--engine-score",
        type=int,
        default=3,
        help="Engine score to include in the prompt (default: 3)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: artifacts/<skill>/llm_judgments.json)",
    )
    args = parser.parse_args()

    skill_path = Path(args.skill)
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"Error: {skill_md} not found", file=sys.stderr)
        return 1

    content = skill_md.read_text(encoding="utf-8")
    judges: List[Dict[str, Any]] = []

    for dimension in args.dimensions:
        prompt = _build_prompt(dimension, content, args.engine_score)
        results: List[Dict[str, Any]] = []
        for i in range(args.count):
            print(f"Judging {dimension} judge {i + 1}/{args.count}...", file=sys.stderr)
            try:
                result = _call_llm(prompt)
                results.append(result)
            except Exception as exc:
                print(f"Warning: judge call failed: {exc}", file=sys.stderr)

        if not results:
            print(f"Warning: no valid results for {dimension}, skipping", file=sys.stderr)
            continue

        scores = [r["score"] for r in results]
        reasons = [r["reason"] for r in results]
        aggregated = _aggregate_scores(scores, args.aggregate)
        judges.append(
            {
                "dimension": dimension,
                "scores": scores,
                "reasons": reasons,
                "aggregated_score": aggregated,
                "aggregate": args.aggregate,
            }
        )

    output_path = (
        Path(args.output)
        if args.output
        else Path("artifacts") / skill_path.name / "llm_judgments.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"judges": judges}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
