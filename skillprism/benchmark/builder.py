#!/usr/bin/env python3
"""Scaffold a benchmark registry entry and generate expected (golden) output.

This makes benchmark construction repeatable and generic across skills.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .download import fetch_dataset
from .runner import load_registry
from .task_spec import load_task_spec


def _parse_metric(spec: str) -> Dict[str, Any]:
    """Parse a metric spec like 'row_count:min:2' or 'n_clusters:range:3:8'."""
    parts = spec.split(":")
    if len(parts) < 3:
        raise ValueError(f"Invalid metric spec: {spec!r}. Use name:type:args, e.g. row_count:min:2")
    name, mtype = parts[0], parts[1]
    metric: Dict[str, Any] = {"id": name, "type": mtype}
    args = parts[2:]
    if mtype in ("min", "max"):
        if len(args) != 1:
            raise ValueError(f"Metric {name!r} of type {mtype!r} needs one threshold argument")
        metric["threshold"] = float(args[0]) if "." in args[0] else int(args[0])
    elif mtype == "range":
        if len(args) != 2:
            raise ValueError(f"Metric {name!r} of type range needs min:max arguments")
        metric["min"] = float(args[0]) if "." in args[0] else int(args[0])
        metric["max"] = float(args[1]) if "." in args[1] else int(args[1])
    elif mtype == "exact":
        if len(args) != 1:
            raise ValueError(f"Metric {name!r} of type exact needs one expected value")
        try:
            metric["expected"] = float(args[0]) if "." in args[0] else int(args[0])
        except ValueError:
            metric["expected"] = args[0]
    elif mtype == "tolerance":
        if len(args) != 1:
            raise ValueError(f"Metric {name!r} of type tolerance needs one threshold argument")
        metric["threshold"] = float(args[0]) if "." in args[0] else int(args[0])
    else:
        raise ValueError(f"Unsupported metric type: {mtype!r}")
    return metric


def _infer_format(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in (".h5ad",):
        return "anndata"
    if suffix == ".csv":
        return "csv"
    if suffix in (".yaml", ".yml"):
        return "yaml"
    if suffix == ".json":
        return "json"
    if suffix in (".md",):
        return "markdown"
    return "unknown"


def build_benchmark_entry(
    bench_id: str,
    name: str,
    skill: str,
    task: str,
    task_spec_path: Optional[str],
    input_path: str,
    expected_path: Optional[str],
    metrics: List[str] | None,
    description: str | None = None,
    level: int = 1,
    requires_gpu: bool = False,
    real_data: bool = False,
) -> Dict[str, Any]:
    """Build a single benchmark registry entry."""
    entry: Dict[str, Any] = {
        "name": name,
        "skill": skill,
        "task": task,
        "level": level,
        "input": {"path": input_path},
    }

    if task_spec_path:
        entry["task_spec"] = task_spec_path
    if description:
        entry["input"]["description"] = description
    if requires_gpu:
        entry["requires_gpu"] = True
    if real_data:
        entry["real_data"] = True

    if expected_path:
        entry["expected"] = {
            "format": _infer_format(expected_path),
            "path": expected_path,
        }

    if metrics:
        entry["metrics"] = [_parse_metric(m) for m in metrics]

    return {bench_id: entry}


def _generate_expected_for_table(
    input_source: str, expected_path: Path, registry_dir: Path
) -> None:
    """For table tasks, copy the input dataset to the expected output path."""
    dataset_spec = {"source": input_source, "type": "local"}
    input_path = fetch_dataset(dataset_spec, registry_dir / ".benchmark_cache")
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_path, expected_path)
    print(f"Expected output generated: {expected_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a skill test registry entry.")
    parser.add_argument("--id", required=True, help="Benchmark unique ID")
    parser.add_argument("--name", required=True, help="Human-readable benchmark name")
    parser.add_argument("--skill", required=True, help="Skill name this benchmark tests")
    parser.add_argument("--task", required=True, help="Task id (e.g. csv_summary)")
    parser.add_argument(
        "--task-spec",
        help="Path to task spec YAML relative to the registry directory (default: tasks/<task>.yaml)",
    )
    parser.add_argument("--input", required=True, help="Input data path (relative to registry)")
    parser.add_argument("--expected-path", help="Relative path to expected (golden) output")
    parser.add_argument(
        "--metric", action="append", help="Metric: id:type:args (e.g. row_count:min:8)"
    )
    parser.add_argument("--description", help="Input description")
    parser.add_argument(
        "--registry",
        default="benchmark_registry.yaml",
        help="Registry YAML to create/append (per-skill: benchmarks/<skill>/registry.yaml)",
    )
    parser.add_argument(
        "--generate-expected",
        action="store_true",
        help="Generate expected output for supported tasks",
    )
    parser.add_argument(
        "--suite",
        action="append",
        help="Add this benchmark to a named suite (can be repeated)",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=[0, 1, 2, 3],
        default=1,
        help="Benchmark difficulty level (0=unit, 1=component, 2=integration, 3=release)",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Mark benchmark as requiring a GPU",
    )
    parser.add_argument(
        "--real-data",
        action="store_true",
        help="Mark benchmark as using real data (not scored; checked for completion)",
    )
    args = parser.parse_args()

    registry_path = Path(args.registry)
    registry_dir = registry_path.parent

    registry = load_registry(registry_path) if registry_path.exists() else {}
    if "benchmarks" not in registry:
        registry["benchmarks"] = {}
    if args.id in registry["benchmarks"]:
        print(f"Error: benchmark id {args.id!r} already exists in {registry_path}")
        return 1

    task_spec_path = args.task_spec
    if not task_spec_path:
        task_spec_path = f"tasks/{args.task}.yaml"

    # Validate task spec exists before registering.
    full_task_spec_path = registry_dir / task_spec_path
    if not full_task_spec_path.exists():
        print(f"Error: task spec not found: {full_task_spec_path}")
        return 1
    load_task_spec(full_task_spec_path)

    entry = build_benchmark_entry(
        bench_id=args.id,
        name=args.name,
        skill=args.skill,
        task=args.task,
        task_spec_path=task_spec_path,
        input_path=args.input,
        expected_path=args.expected_path,
        metrics=args.metric,
        description=args.description,
        level=args.level,
        requires_gpu=args.gpu,
        real_data=args.real_data,
    )

    registry["benchmarks"].update(entry)

    # Add to suites if requested
    if args.suite:
        if "suites" not in registry:
            registry["suites"] = {}
        for suite_name in args.suite:
            suite = registry["suites"].setdefault(suite_name, {"benchmarks": []})
            if args.id not in suite["benchmarks"]:
                suite["benchmarks"].append(args.id)

    # Ensure schema/cache metadata exist
    if "schema_version" not in registry:
        registry["schema_version"] = "2.0"
    if "cache_dir" not in registry:
        registry["cache_dir"] = ".benchmark_cache"

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8") as f:
        yaml.dump(registry, f, allow_unicode=True, sort_keys=False)
    print(f"Benchmark registered in: {registry_path}")

    if args.generate_expected:
        inferred_format = _infer_format(args.expected_path) if args.expected_path else ""
        if inferred_format == "csv":
            expected_full = registry_dir / args.expected_path
            _generate_expected_for_table(args.input, expected_full, registry_dir)
        else:
            print("Warning: --generate-expected only supports csv tasks")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
