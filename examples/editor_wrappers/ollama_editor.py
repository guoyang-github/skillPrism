#!/usr/bin/env python3
"""Example SKILL.md editor using a local Ollama server.

Usage:
    export OLLAMA_MODEL=llama3
    # Ensure ollama is running on http://localhost:11434
    cat prompt.txt | python ollama_editor.py > updated_SKILL.md

Install dependencies:
    pip install requests
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        import requests
    except ImportError as exc:
        print(
            "Error: requests is not installed. Run `pip install requests`.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    model = os.environ.get("OLLAMA_MODEL", "llama3")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    prompt = sys.stdin.read()

    response = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "system": (
                "You are an expert SKILL.md editor for AI agent skills. "
                "Return ONLY the complete updated SKILL.md content as plain Markdown. "
                "Do not wrap it in code fences, do not add explanations."
            ),
            "stream": False,
            "options": {"temperature": 0.2},
        },
        timeout=300,
    )
    response.raise_for_status()

    content = response.json().get("response", "")
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("markdown"):
            content = content[len("markdown") :].strip()
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
