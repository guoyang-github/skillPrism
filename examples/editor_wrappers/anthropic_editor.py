#!/usr/bin/env python3
"""Example SKILL.md editor using the Anthropic API.

Usage:
    export ANTHROPIC_API_KEY=...
    export ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
    cat prompt.txt | python anthropic_editor.py > updated_SKILL.md

Install dependencies:
    pip install anthropic
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        import anthropic
    except ImportError as exc:
        print(
            "Error: anthropic is not installed. Run `pip install anthropic`.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        return 1

    model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    prompt = sys.stdin.read()

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=(
            "You are an expert SKILL.md editor for AI agent skills. "
            "Return ONLY the complete updated SKILL.md content as plain Markdown. "
            "Do not wrap it in code fences, do not add explanations."
        ),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    content = response.content[0].text if response.content else ""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("markdown"):
            content = content[len("markdown") :].strip()
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
