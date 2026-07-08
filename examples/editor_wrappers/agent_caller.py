#!/usr/bin/env python3
"""Example external agent command for skillPrism benchmark execution.

This wrapper simulates an external agent that receives a task prompt and writes
a result to the expected output path. In a real setup, this script would call an
LLM or another agent framework to produce the output.

Usage with skillPrism:
    export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
    test-skill --skill my-skill --task csv_summary

The command receives:
- stdin: the task prompt generated from the task spec
- environment variables:
  - SKILLPRISM_INPUT_PATH: concrete input file path
  - SKILLPRISM_OUTPUT_PATH: expected output file path

It is expected to write the result to SKILLPRISM_OUTPUT_PATH and exit 0.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    prompt = sys.stdin.read()
    input_path = os.environ.get("SKILLPRISM_INPUT_PATH", "")
    output_path = os.environ.get("SKILLPRISM_OUTPUT_PATH", "")

    if not input_path or not output_path:
        print(
            "Error: SKILLPRISM_INPUT_PATH and SKILLPRISM_OUTPUT_PATH must be set.",
            file=sys.stderr,
        )
        return 1

    # Minimal deterministic fallback: copy input to output if format matches.
    # In a real agent command, this is where the LLM/agent reasoning happens.
    in_file = Path(input_path)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if in_file.exists():
        out_file.write_text(in_file.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        out_file.write_text(
            f"Agent placeholder output for prompt:\n{prompt[:200]}", encoding="utf-8"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
