#!/usr/bin/env python3
"""Tests for the AgentExecutor."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillprism.benchmark.executors import AgentExecutor


def test_agent_executor_runs_command_and_returns_output_path(tmp_path):
    input_file = tmp_path / "input.txt"
    output_file = tmp_path / "output.txt"
    input_file.write_text("hello")

    script = tmp_path / "agent.py"
    script.write_text(
        "import os\n"
        "inp = os.environ['SKILLPRISM_INPUT_PATH']\n"
        "out = os.environ['SKILLPRISM_OUTPUT_PATH']\n"
        "with open(inp, 'r') as f: data = f.read()\n"
        "with open(out, 'w') as f: f.write(data.upper())\n"
    )

    task_spec = {
        "input": {"path": "{input_file}"},
        "output": {"path": "{output_file}"},
    }
    benchmark = {
        "input": {"path": str(input_file)},
        "output": {"path": str(output_file)},
    }

    executor = AgentExecutor([sys.executable, str(script)])
    result_path = executor.execute(task_spec, benchmark, "task prompt")

    assert result_path == output_file
    assert output_file.read_text() == "HELLO"
