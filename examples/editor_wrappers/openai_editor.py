#!/usr/bin/env python3
"""Example SKILL.md editor using the OpenAI API.

Usage:
    export OPENAI_API_KEY=...
    export OPENAI_MODEL=gpt-4o-mini
    cat prompt.txt | python openai_editor.py > updated_SKILL.md

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

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    prompt = sys.stdin.read()

    client = openai.OpenAI(api_key=api_key)
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
