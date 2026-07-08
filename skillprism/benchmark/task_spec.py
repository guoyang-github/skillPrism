#!/usr/bin/env python3
"""Task specification loader, validator, and prompt generator for benchmarks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Set, cast

import yaml

REQUIRED_TASK_FIELDS: Set[str] = {
    "id",
    "skill",
    "name",
    "description",
    "prompt",
    "input",
    "output",
}
REQUIRED_IO_FIELDS: Set[str] = {"format", "path"}


def load_task_spec(path: Path) -> Dict[str, Any]:
    """Load a task spec YAML file and validate it."""
    with path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f) or {}
    validate_task_spec(spec)
    return spec


def validate_task_spec(spec: Dict[str, Any]) -> None:
    """Raise ValueError if the task spec is invalid."""
    missing = REQUIRED_TASK_FIELDS - set(spec.keys())
    if missing:
        raise ValueError(f"Task spec missing required fields: {sorted(missing)}")

    for section in ("input", "output"):
        io = spec[section]
        if not isinstance(io, dict):
            raise ValueError(f"Task spec '{section}' must be a mapping")
        missing_io = REQUIRED_IO_FIELDS - set(io.keys())
        if missing_io:
            raise ValueError(f"Task spec '{section}' missing fields: {sorted(missing_io)}")

    _validate_prompt_placeholders(spec)


def _validate_prompt_placeholders(spec: Dict[str, Any]) -> None:
    """Ensure prompt placeholders match input/output path placeholders."""
    prompt = spec["prompt"]
    placeholders = set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", prompt))
    io_placeholders = {spec["input"]["path"], spec["output"]["path"]}
    io_placeholders = {p.strip("{}") for p in io_placeholders if isinstance(p, str)}

    missing = io_placeholders - placeholders
    if missing:
        raise ValueError(f"Prompt missing placeholders for input/output paths: {sorted(missing)}")


def resolve_variables(task_spec: Dict[str, Any], benchmark: Dict[str, Any]) -> Dict[str, str]:
    """Resolve input/output placeholders using a benchmark registry entry."""
    variables: Dict[str, str] = {}

    input_path = _resolve_io_path(task_spec["input"], benchmark.get("input"), "input")
    output_path = _resolve_io_path(task_spec["output"], benchmark.get("output"), "output")

    input_placeholder = _extract_placeholder(task_spec["input"]["path"])
    output_placeholder = _extract_placeholder(task_spec["output"]["path"])

    variables[input_placeholder] = str(input_path)
    variables[output_placeholder] = str(output_path)

    return variables


def _extract_placeholder(path_template: str) -> str:
    """Extract the placeholder name from a path template like '{input_csv}'."""
    match = re.search(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", path_template)
    if not match:
        raise ValueError(f"Path template has no placeholder: {path_template!r}")
    return match.group(1)


def _resolve_io_path(
    io_spec: Dict[str, Any],
    benchmark_io: Optional[Dict[str, Any]],
    section: str,
) -> Path:
    """Resolve the actual filesystem path for an input or output section."""
    if benchmark_io and "path" in benchmark_io:
        return Path(benchmark_io["path"])

    # Fallback: use the path template literally if it does not contain placeholders.
    path_template = io_spec["path"]
    if "{" not in path_template:
        return Path(path_template)

    raise ValueError(f"Benchmark missing '{section}.path' and task spec path is templated")


def generate_agent_prompt(task_spec: Dict[str, Any], benchmark: Dict[str, Any]) -> str:
    """Generate the final prompt by replacing placeholders with real paths."""
    template = cast(str, task_spec["prompt"])
    variables = resolve_variables(task_spec, benchmark)
    return template.format(**variables)


def find_task_spec(skill: str, task: str, search_root: Optional[Path] = None) -> Path:
    """Discover a task spec file for a given skill and task id."""
    if search_root is None:
        search_root = Path("benchmarks")

    candidate = search_root / skill / "tasks" / f"{task}.yaml"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Task spec not found: {candidate}")
