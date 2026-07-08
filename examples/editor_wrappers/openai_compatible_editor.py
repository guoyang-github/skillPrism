#!/usr/bin/env python3
"""Example SKILL.md editor using any OpenAI-compatible API.

This wrapper works with most Chinese LLM providers that expose an OpenAI-compatible
chat completions endpoint, including:

- Moonshot (Kimi): https://api.moonshot.cn/v1
- DeepSeek: https://api.deepseek.com
- Zhipu AI (GLM): https://open.bigmodel.cn/api/paas/v4/
- Alibaba DashScope (Qwen): https://dashscope.aliyuncs.com/compatible-mode/v1

Usage:
    export OPENAI_API_KEY=<your-api-key>
    export OPENAI_BASE_URL=https://api.moonshot.cn/v1
    export OPENAI_MODEL=moonshot-v1-8k
    cat prompt.txt | python openai_compatible_editor.py > updated_SKILL.md

Install dependencies:
    pip install openai
"""

from __future__ import annotations

import os
import sys


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
                    "You are an expert SKILL.md editor for AI agent skills. "
                    "Return ONLY the complete updated SKILL.md content as plain Markdown. "
                    "Do not wrap it in code fences, do not add explanations."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content or ""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("markdown"):
            content = content[len("markdown") :].strip()
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
