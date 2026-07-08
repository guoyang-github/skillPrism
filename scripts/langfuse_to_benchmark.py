#!/usr/bin/env python3
"""Generate a benchmark entry from a Langfuse trace or dataset item.

This lowers the cost of building benchmarks: instead of hand-writing task specs,
input data, and expected output, you can turn a real production trace into a
regression test.

Usage:
    export LANGFUSE_HOST=https://your-langfuse.com
    export LANGFUSE_PUBLIC_KEY=pk-...
    export LANGFUSE_SECRET_KEY=sk-...

    python scripts/langfuse_to_benchmark.py \
        --trace-id <trace-id> \
        --registry benchmarks/<skill>/registry.yaml \
        --suite smoke

The script will:
1. Fetch the trace from Langfuse.
2. Read skill_name and task from the trace metadata.
3. Write the input to benchmarks/<skill>/data/<task>/input.<fmt>.
4. Write the output to benchmarks/<skill>/expected/<task>.<fmt>.
5. Generate benchmarks/<skill>/tasks/<task>.yaml if it does not exist.
6. Append a benchmark entry to benchmarks/<skill>/registry.yaml.

If the trace does not have an expected output, the current output is used as a
completion-only golden standard. Always review the generated expected output
before committing it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import yaml


def _get_langfuse_client() -> Any:
    try:
        from langfuse import Langfuse
    except ImportError as exc:
        print("Error: langfuse is not installed. Run `pip install langfuse`.", file=sys.stderr)
        raise SystemExit(1) from exc

    host = os.environ.get("LANGFUSE_HOST")
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not host or not public_key or not secret_key:
        print(
            "Error: LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )


def _infer_format(value: Any) -> str:
    """Infer file format from a value."""
    if isinstance(value, dict):
        return "json"
    if isinstance(value, list):
        return "json"
    text = str(value)
    if text.strip().startswith("[") or text.strip().startswith("{"):
        return "json"
    lines = text.strip().splitlines()
    if len(lines) > 1 and "," in lines[0]:
        return "csv"
    return "markdown"


def _write_data_file(path: Path, value: Any, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path.write_text(str(value), encoding="utf-8")


def _generate_task_spec(
    skill: str,
    task: str,
    input_path: Path,
    output_path: Path,
    input_fmt: str,
    output_fmt: str,
    registry_dir: Path,
) -> Dict[str, Any]:
    placeholder = f"{skill}_{task}_input".replace("-", "_")
    output_placeholder = f"{skill}_{task}_output".replace("-", "_")
    return {
        "id": task,
        "skill": skill,
        "name": f"{skill}: {task}",
        "description": f"Auto-generated benchmark for {skill} task {task}.",
        "prompt": (
            f"Run the '{skill}' skill on {{{{{placeholder}}}}} and write the result to "
            f"{{{{{output_placeholder}}}}}"
        ),
        "input": {"format": input_fmt, "path": f"{{{placeholder}}}"},
        "output": {"format": output_fmt, "path": f"{{{output_placeholder}}}"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a benchmark entry from a Langfuse trace or dataset item."
    )
    parser.add_argument("--trace-id", help="Langfuse trace ID")
    parser.add_argument("--dataset-item-id", help="Langfuse dataset item ID")
    parser.add_argument("--registry", default="benchmark_registry.yaml", help="Registry YAML")
    parser.add_argument("--suite", action="append", help="Add to suite (repeatable)")
    parser.add_argument("--benchmark-id", help="Override benchmark ID")
    parser.add_argument("--task", help="Override task ID")
    parser.add_argument("--input-format", help="Force input format")
    parser.add_argument("--output-format", help="Force output format")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done")
    args = parser.parse_args()

    if not args.trace_id and not args.dataset_item_id:
        print("Error: --trace-id or --dataset-item-id is required.", file=sys.stderr)
        return 2

    client = _get_langfuse_client()

    if args.trace_id:
        trace = client.client.trace.get(args.trace_id)
        metadata = trace.metadata or {}
        input_value = trace.input
        output_value = trace.output
    else:
        item = client.client.dataset_items.get(args.dataset_item_id)
        metadata = item.metadata or {}
        input_value = item.input
        output_value = item.expected_output

    skill = metadata.get("skill_name")
    task = args.task or metadata.get("task") or metadata.get("task_id")
    if not skill or not task:
        print(
            f"Error: trace metadata must include 'skill_name' and 'task'/'task_id'. "
            f"Got metadata keys: {sorted(metadata.keys())}",
            file=sys.stderr,
        )
        return 2

    registry_path = Path(args.registry)
    registry_dir = registry_path.parent or Path(".")
    data_dir = registry_dir / "data" / task
    expected_dir = registry_dir / "expected"
    task_spec_path = registry_dir / "tasks" / f"{task}.yaml"

    input_fmt = args.input_format or _infer_format(input_value)
    output_fmt = args.output_format or _infer_format(output_value)
    input_file = data_dir / f"input.{input_fmt}"
    expected_file = expected_dir / f"{task}.{output_fmt}"

    bench_id = args.benchmark_id or f"{skill}_{task}_auto"

    print(f"Skill: {skill}")
    print(f"Task: {task}")
    print(f"Input file: {input_file}")
    print(f"Expected output: {expected_file}")
    print(f"Task spec: {task_spec_path}")
    print(f"Benchmark ID: {bench_id}")

    if args.dry_run:
        print("Dry run: no files written.")
        return 0

    _write_data_file(input_file, input_value, input_fmt)
    _write_data_file(expected_file, output_value, output_fmt)

    if not task_spec_path.exists():
        task_spec = _generate_task_spec(
            skill, task, input_file, expected_file, input_fmt, output_fmt, registry_dir
        )
        task_spec_path.parent.mkdir(parents=True, exist_ok=True)
        task_spec_path.write_text(
            yaml.safe_dump(task_spec, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        print(f"Created task spec: {task_spec_path}")
    else:
        print(f"Task spec already exists: {task_spec_path}")

    from skillprism.benchmark.builder import build_benchmark_entry
    from skillprism.benchmark.runner import load_registry

    registry = load_registry(registry_path) if registry_path.exists() else {}
    if "benchmarks" not in registry:
        registry["benchmarks"] = {}
    if bench_id in registry["benchmarks"]:
        print(f"Error: benchmark id {bench_id!r} already exists in {registry_path}")
        return 1

    entry = build_benchmark_entry(
        bench_id=bench_id,
        name=f"{skill}: {task}",
        skill=skill,
        task=task,
        task_spec_path=str(task_spec_path.relative_to(registry_dir)),
        input_path=str(input_file.relative_to(registry_dir)),
        expected_path=str(expected_file.relative_to(registry_dir)),
        metrics=None,
        level=1,
        requires_gpu=False,
        real_data=False,
    )
    registry["benchmarks"].update(entry)
    if args.suite:
        suites = registry.setdefault("suites", {})
        for suite in args.suite:
            suites.setdefault(suite, {"benchmarks": []})["benchmarks"].append(bench_id)

    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"Updated registry: {registry_path}")
    print("Reminder: review the generated expected output before committing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
