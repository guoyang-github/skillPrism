#!/usr/bin/env python3
"""Example LLM-as-judge caller using any OpenAI-compatible API.

This wrapper works with most Chinese LLM providers that expose an OpenAI-compatible
chat completions endpoint, including:

- Moonshot (Kimi): https://api.moonshot.cn/v1
- DeepSeek: https://api.deepseek.com
- Zhipu AI (GLM): https://open.bigmodel.cn/api/paas/v4/
- Alibaba DashScope (Qwen): https://dashscope.aliyuncs.com/compatible-mode/v1

Usage with skillPrism:
    export OPENAI_API_KEY=<your-api-key>
    export OPENAI_BASE_URL=https://api.moonshot.cn/v1
    export OPENAI_MODEL=moonshot-v1-8k
    export SKILLPRISM_LLM_JUDGE_COMMAND="python examples/editor_wrappers/openai_compatible_judge.py"
    evaluate-skill skills/my-skill --llm-judge

Install dependencies:
    pip install openai
"""

from __future__ import annotations

import json
import os
import sys


def _extract_json(text: str) -> str:
    """Try to extract the first JSON object from the response."""
    text = text.strip()
    # If wrapped in markdown fences, strip them.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def main() -> int:
    try:
        import openai
    except ImportError as exc:
        print("Error: openai is not installed. Run `pip install openai`.", file=sys.stderr)
        raise SystemExit(1) from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY is not set.", file=sys.stderr)
        return 1

    base_url = os.environ.get("OPENAI_BASE_URL")
    if not base_url:
        print(
            "Error: OPENAI_BASE_URL is not set. Set it to the OpenAI-compatible endpoint, "
            "e.g. https://api.moonshot.cn/v1",
            file=sys.stderr,
        )
        return 1

    model = os.environ.get("OPENAI_MODEL")
    if not model:
        print(
            "Error: OPENAI_MODEL is not set. Set it to the model name, "
            "e.g. moonshot-v1-8k or deepseek-chat.",
            file=sys.stderr,
        )
        return 1

    prompt = sys.stdin.read()

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

    try:
        data = json.loads(content)
        score = int(float(data["score"]))
        reason = str(data.get("reason", "")).strip()
        # Validate and clamp.
        score = max(1, min(5, score))
        print(json.dumps({"score": score, "reason": reason}, ensure_ascii=False))
    except Exception as exc:
        # Do NOT emit a valid score JSON on failure. The engine's llm_judge
        # treats empty stdout + non-zero exit as a parse failure and retries
        # (and eventually drops the judgment). Emitting a silent 3/5 here would
        # defeat that: every outage or malformed response would blend a neutral
        # 3 into the rubric. Surface the error to stderr and exit non-zero.
        print(f"Judge parsing failed: {exc}", file=sys.stderr)
        print(f"Raw response was: {content[:500]!r}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
