#!/usr/bin/env python3
"""Generate benchmark execution code from SKILL.md and a benchmark registry.

This script is intentionally LLM-agnostic: it builds a prompt and calls an
external command (default from SKILLPRISM_CODE_GENERATOR_COMMAND) to produce
the code. skillPrism itself does not call LLMs.

Usage:
    python scripts/skill_code_generator.py \
        skills/my-skill \
        --registry benchmarks/my-skill/registry.yaml \
        --benchmark my_bench_id \
        --output benchmarks/my-skill/runner.py

The generated code is expected to use the task-specific injected variables:

    table:          input_csv, output_csv, output_dir
    clustering:     adata, sc
    document:       prompt_path, output_path, output_dir
    deconvolution:  input_dir, output_csv, output_dir
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skillprism.code_generator import generate_skill_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate benchmark execution code from SKILL.md.")
    parser.add_argument("skill", help="Path to the skill directory")
    parser.add_argument("--registry", required=True, help="Benchmark registry YAML")
    parser.add_argument("--benchmark", required=True, help="Benchmark ID in the registry")
    parser.add_argument("--output", required=True, help="Output path for generated code")
    parser.add_argument(
        "--generator-command",
        help="Command to call the code generator (overrides env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the prompt instead of generating code",
    )
    args = parser.parse_args()

    skill_path = Path(args.skill).resolve()
    registry_path = Path(args.registry).resolve()
    output_path = Path(args.output).resolve()

    if not skill_path.is_dir():
        print(f"Error: {skill_path} is not a directory", file=sys.stderr)
        return 2

    if args.dry_run:
        from skillprism.code_generator import build_prompt, load_registry, load_skill_md

        registry = load_registry(registry_path)
        benchmark = registry.get("benchmarks", {}).get(args.benchmark)
        if not benchmark:
            print(f"Error: benchmark {args.benchmark!r} not found", file=sys.stderr)
            return 2
        task = benchmark.get("task")
        from skillprism.code_generator import TASK_VARIABLES

        variables = TASK_VARIABLES.get(task)
        if variables is None:
            print(f"Error: unsupported task {task!r}", file=sys.stderr)
            return 2
        skill_md = load_skill_md(skill_path)
        prompt = build_prompt(skill_md, benchmark, task, variables)
        print(prompt)
        return 0

    try:
        generated = generate_skill_code(
            skill_path, registry_path, args.benchmark, args.generator_command
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated, encoding="utf-8")
    print(f"Generated code written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
