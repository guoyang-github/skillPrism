#!/usr/bin/env python3
"""Benchmark executors: produce the actual output from a task spec."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .sandbox import run_user_code
from .task_spec import resolve_variables


class Executor:
    """Base executor: turn a task spec + benchmark into an actual output path."""

    def execute(
        self,
        task_spec: Dict[str, Any],
        benchmark: Dict[str, Any],
        prompt: str,
        code_path: Optional[Path] = None,
    ) -> Path:
        raise NotImplementedError


class CodeExecutor(Executor):
    """Execute a user-supplied Python script against the benchmark input.

    The script runs in a sandboxed child process (see ``sandbox.run_user_code``):
    separate process, minimal environment, cwd jail to the output dir, and
    rlimit caps on memory/CPU/file-size. It is **never** exec'd in-process.
    """

    def execute(
        self,
        task_spec: Dict[str, Any],
        benchmark: Dict[str, Any],
        prompt: str,
        code_path: Optional[Path] = None,
    ) -> Path:
        if code_path is None or not code_path.exists():
            raise ValueError("CodeExecutor requires a valid --code path")

        variables = resolve_variables(task_spec, benchmark)
        output_path = Path(variables[_extract_placeholder(task_spec["output"]["path"])])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Resolve path variables to absolute so the sandboxed child (whose cwd is
        # the output dir) can locate inputs/outputs regardless of the parent cwd.
        variables = {k: str(Path(v).resolve()) for k, v in variables.items()}

        skill_code = code_path.read_text(encoding="utf-8")
        try:
            proc = run_user_code(skill_code, variables, output_path.parent)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Skill code timed out after {e.timeout}s") from e
        if proc.returncode != 0:
            raise RuntimeError(f"Skill code failed (exit {proc.returncode}): {proc.stderr[:1000]}")

        if not output_path.exists():
            raise RuntimeError(f"Executed code did not produce expected output: {output_path}")
        return output_path


class AgentExecutor(Executor):
    """Invoke an external agent command to produce the benchmark output.

    The command receives the task prompt on stdin and the concrete input/output
    paths via the environment variables ``SKILLPRISM_INPUT_PATH`` and
    ``SKILLPRISM_OUTPUT_PATH``. The agent is expected to write the result to the
    output path and exit with code 0.
    """

    def __init__(self, command: List[str]) -> None:
        self.command = command

    def execute(
        self,
        task_spec: Dict[str, Any],
        benchmark: Dict[str, Any],
        prompt: str,
        code_path: Optional[Path] = None,
    ) -> Path:
        variables = resolve_variables(task_spec, benchmark)
        input_path = Path(variables[_extract_placeholder(task_spec["input"]["path"])])
        output_path = Path(variables[_extract_placeholder(task_spec["output"]["path"])])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        executable = shutil.which(self.command[0])
        if executable is None:
            raise RuntimeError(f"Agent command not found: {self.command[0]}")
        cmd = [executable] + self.command[1:]

        # Minimal environment: do NOT copy the parent env wholesale (which would
        # leak secrets, SKILLPRISM_* tokens, and unrelated config into the agent
        # subprocess). The agent command is user-configured, so callers who need
        # credentials forwarded list them in SKILLPRISM_AGENT_PASS_THROUGH_ENV
        # (comma-separated); nothing extra is passed by default.
        env = {
            "PATH": os.environ.get(
                "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            ),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "TERM": os.environ.get("TERM", "dumb"),
            "SKILLPRISM_INPUT_PATH": str(input_path),
            "SKILLPRISM_OUTPUT_PATH": str(output_path),
        }
        pass_through = os.environ.get("SKILLPRISM_AGENT_PASS_THROUGH_ENV", "")
        for key in (k.strip() for k in pass_through.split(",") if k.strip()):
            if key in os.environ:
                env[key] = os.environ[key]

        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Agent command failed (exit {proc.returncode}): {proc.stderr[:500]}"
            )

        if not output_path.exists():
            raise RuntimeError(f"Agent command did not produce expected output: {output_path}")
        return output_path


def _extract_placeholder(path_template: str) -> str:
    """Return the placeholder name inside a path template like '{output_csv}'."""
    import re

    match = re.search(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", path_template)
    if not match:
        raise ValueError(f"Path template has no placeholder: {path_template!r}")
    return match.group(1)
