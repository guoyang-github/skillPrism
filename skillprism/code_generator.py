#!/usr/bin/env python3
"""Generate benchmark execution code from SKILL.md and a benchmark registry.

This module is intentionally LLM-agnostic: it builds a prompt and calls an
external command (default from SKILLPRISM_CODE_GENERATOR_COMMAND) to produce
the code. skillPrism itself does not call LLMs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, cast

import yaml

TASK_VARIABLES = {
    "table": ["input_csv", "output_csv", "output_dir"],
    "clustering": ["adata", "sc"],
    "document": ["prompt_path", "output_path", "output_dir"],
    "deconvolution": ["input_dir", "output_csv", "output_dir"],
}


def load_registry(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return cast(Dict[str, Any], yaml.safe_load(f) or {})


def load_skill_md(skill_path: Path) -> str:
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"{skill_md} not found")
    return skill_md.read_text(encoding="utf-8", errors="replace")


def build_prompt(
    skill_md: str,
    benchmark: Dict[str, Any],
    task: str,
    variables: list[str],
) -> str:
    dataset = benchmark.get("dataset", {})
    expected = benchmark.get("expected") or benchmark.get("expected_output") or {}
    metrics = benchmark.get("metrics", [])

    lines = [
        "You are a code generator for the skillPrism benchmark framework.",
        "Read the SKILL.md below and generate a complete, self-contained Python script",
        "that can be executed by the benchmark runner to produce the expected output.",
        "",
        f"Benchmark task: {task}",
        f"Available variables (injected by the runner): {', '.join(variables)}",
        f"Dataset spec: {dataset}",
        f"Expected output spec: {expected}",
        f"Metrics to satisfy: {metrics}",
        "",
        "Requirements:",
        "- Use only the injected variables; do not parse command-line arguments.",
        "- Write the output to the path indicated by the injected variables.",
        "- Keep the code minimal and deterministic.",
        "- Include necessary imports.",
        "- Do not wrap the code in markdown fences.",
        "",
        "SKILL.md:",
        "---",
        skill_md[:12000],
        "---",
    ]
    return "\n".join(lines)


def get_generator_command() -> Optional[str]:
    return os.environ.get("SKILLPRISM_CODE_GENERATOR_COMMAND")


def run_generator(prompt: str, command: Optional[str] = None) -> str:
    cmd = command or get_generator_command()
    if not cmd:
        raise RuntimeError(
            "No code generator command configured. "
            "Set SKILLPRISM_CODE_GENERATOR_COMMAND or pass --generator-command."
        )

    parts = cmd.split()
    executable = shutil.which(parts[0])
    if executable is None:
        raise RuntimeError(f"Generator command not found: {parts[0]}")

    proc = subprocess.run(
        [executable] + parts[1:],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Code generator failed: {proc.stderr[:500]}")
    return proc.stdout.strip()


def generate_skill_code(
    skill_path: Path,
    registry_path: Path,
    benchmark_id: str,
    generator_command: Optional[str] = None,
) -> str:
    """Generate benchmark execution code for a single benchmark.

    Args:
        skill_path: Path to the skill directory containing SKILL.md.
        registry_path: Path to the benchmark registry YAML.
        benchmark_id: ID of the benchmark in the registry.
        generator_command: Optional override for the external generator command.

    Returns:
        Generated code as a string.
    """
    registry = load_registry(registry_path)
    benchmark = registry.get("benchmarks", {}).get(benchmark_id)
    if not benchmark:
        raise ValueError(f"Benchmark {benchmark_id!r} not found in {registry_path}")

    task = benchmark.get("task")
    variables = TASK_VARIABLES.get(task)
    if variables is None:
        raise ValueError(f"Unsupported task {task!r}")

    skill_md = load_skill_md(skill_path)
    prompt = build_prompt(skill_md, benchmark, task, variables)
    return run_generator(prompt, generator_command)


def find_benchmark_for_skill(
    registry_path: Path,
    skill_name: str,
) -> Optional[str]:
    """Return the first benchmark in the registry that matches the given skill."""
    registry = load_registry(registry_path)
    for bid, benchmark in registry.get("benchmarks", {}).items():
        if benchmark.get("skill") == skill_name or skill_name in benchmark.get("skills", []):
            return cast(str, bid)
    return None
