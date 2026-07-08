#!/usr/bin/env python3
"""Run benchmarks from a registry and report pass/fail."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import yaml

from .download import fetch_dataset
from .evaluators import GenericEvaluator
from .executors import AgentExecutor, CodeExecutor
from .task_spec import (
    generate_agent_prompt,
    load_task_spec,
)


def _load_local_metrics(registry_dir: Path) -> None:
    """Load per-registry metric registrations from ``metrics.py`` if present."""
    metrics_py = registry_dir / "metrics.py"
    if not metrics_py.exists():
        return
    spec = importlib.util.spec_from_file_location("local_metrics", metrics_py)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def load_registry(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _prepare_input_path(
    task_spec: Dict[str, Any],
    benchmark: Dict[str, Any],
    registry_dir: Path,
    cache_dir: Path,
) -> Path:
    """Resolve the input path and fetch remote/builtin data if necessary."""
    input_spec = benchmark.get("input") or {}
    path_template = task_spec["input"]["path"]

    # If the benchmark defines a concrete input path, use it.
    if input_spec.get("path"):
        input_path = Path(input_spec["path"])
        if not input_path.is_absolute():
            input_path = registry_dir / input_path
        return input_path

    # Otherwise, derive from the template and fetch the dataset.
    placeholder = re.search(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", path_template)
    if not placeholder:
        raise ValueError(f"Task spec input path has no placeholder: {path_template}")
    var_name = placeholder.group(1)

    dataset_spec = benchmark.get("dataset")
    if not dataset_spec:
        raise ValueError(f"Benchmark {benchmark.get('_id')} has no input.path or dataset spec")

    fetched = fetch_dataset(dataset_spec, cache_dir)
    if isinstance(fetched, Path):
        input_path = fetched
    else:
        # Builtin datasets may return an object; save to cache as a file.
        input_path = cache_dir / f"{benchmark.get('_id', 'unknown')}_{var_name}"
        input_path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(fetched, "write_h5ad"):
            fetched.write_h5ad(input_path)
        elif hasattr(fetched, "write"):
            fetched.write(input_path)
        elif hasattr(fetched, "to_csv"):
            fetched.to_csv(input_path, index=False)
        else:
            raise ValueError(f"Unsupported fetched dataset type: {type(fetched)}")

    if not input_path.is_absolute():
        input_path = registry_dir / input_path
    return input_path


def _resolve_output_path(
    task_spec: Dict[str, Any],
    benchmark: Dict[str, Any],
    cache_dir: Path,
) -> Path:
    """Resolve the output path for a benchmark run."""
    output_spec = benchmark.get("output") or benchmark.get("expected_output") or {}
    if output_spec.get("path"):
        output_path = Path(output_spec["path"])
        if not output_path.is_absolute():
            output_path = cache_dir / output_path
    else:
        bench_id = benchmark.get("_id", "unknown")
        ext = task_spec["output"]["format"]
        # Normalize common format names to conventional file extensions.
        ext = {"markdown": "md"}.get(ext, ext)
        output_path = cache_dir / "output" / bench_id / f"output.{ext}"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _task_spec_path_for_benchmark(benchmark: Dict[str, Any], registry_dir: Path) -> Path:
    """Locate the task spec file for a benchmark."""
    explicit = benchmark.get("task_spec")
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = registry_dir / path
        return path

    task = cast(str, benchmark.get("task"))
    if not task:
        raise ValueError(f"Benchmark {benchmark.get('_id')} missing task for task discovery")
    return registry_dir / "tasks" / f"{task}.yaml"


def run_single_benchmark(
    benchmark: Dict[str, Any],
    skill: str,
    code_path: Optional[Path],
    registry: Dict[str, Any],
    registry_dir: Path,
    verify_only: bool = False,
    agent_command: Optional[List[str]] = None,
) -> Dict[str, Any]:
    cache_dir = Path(registry.get("cache_dir", ".benchmark_cache"))
    if not cache_dir.is_absolute():
        cache_dir = registry_dir / cache_dir

    # Plugin dispatch: if a registered plugin task matches the benchmark's
    # ``task`` field, delegate to it (the plugin returns a full result dict).
    from .plugins import get_task

    task_name = benchmark.get("task")
    if task_name:
        plugin_fn = get_task(str(task_name))
        if plugin_fn is not None:
            try:
                return plugin_fn(benchmark, skill, code_path, registry, registry_dir)
            except Exception as exc:
                return {"error": f"plugin '{task_name}' failed: {exc}", "_all_pass": False}

    try:
        _load_local_metrics(registry_dir)

        task_spec_path = _task_spec_path_for_benchmark(benchmark, registry_dir)
        task_spec = load_task_spec(task_spec_path)

        input_path = _prepare_input_path(task_spec, benchmark, registry_dir, cache_dir)
        output_path = _resolve_output_path(task_spec, benchmark, cache_dir)

        # Inject concrete paths into the benchmark for variable resolution.
        benchmark.setdefault("input", {})["path"] = str(input_path)
        benchmark.setdefault("output", {})["path"] = str(output_path)

        prompt = generate_agent_prompt(task_spec, benchmark)

        if verify_only:
            actual_path = output_path
            if not actual_path.exists():
                return {
                    "error": f"verify-only mode but output not found: {actual_path}",
                    "_all_pass": False,
                }
        else:
            if agent_command is not None:
                executor = AgentExecutor(agent_command)
                actual_path = executor.execute(task_spec, benchmark, prompt)
            elif code_path is not None and code_path.exists():
                code_executor = CodeExecutor()
                actual_path = code_executor.execute(task_spec, benchmark, prompt, code_path)
            else:
                return {
                    "error": "No executor available. Use --code to run generated code, "
                    "set SKILLPRISM_AGENT_COMMAND for agent mode, "
                    "or --verify-only to evaluate an existing output.",
                    "_all_pass": False,
                }

        expected_path = None
        expected_spec = benchmark.get("expected") or benchmark.get("expected_output")
        if expected_spec and expected_spec.get("path"):
            expected_path = Path(expected_spec["path"])
            if not expected_path.is_absolute():
                expected_path = registry_dir / expected_path

        evaluator = GenericEvaluator()
        metrics_spec = benchmark.get("metrics", [])
        result = evaluator.evaluate(actual_path, expected_path, metrics_spec, task_spec)

        result["_actual_output"] = str(actual_path)
        if expected_path:
            result["_expected_output"] = str(expected_path)
        return result

    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "_all_pass": False}


def _has_gpu() -> bool:
    """Best-effort check for an available CUDA GPU."""
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


def _filter_benchmarks(
    benchmarks: Dict[str, Any],
    suite_name: Optional[str],
    level: Optional[int],
    registry: Dict[str, Any],
) -> List[str]:
    """Return ordered benchmark ids filtered by suite and/or level."""
    if suite_name:
        suites = registry.get("suites", {}) or {}
        suite = suites.get(suite_name)
        if not suite:
            raise ValueError(
                f"Suite {suite_name!r} not found. Available suites: {list(suites.keys())}"
            )
        ids = list(suite.get("benchmarks", []))
    else:
        ids = list(benchmarks.keys())

    if level is not None:
        ids = [bid for bid in ids if benchmarks.get(bid, {}).get("level") == level]

    return ids


def _evaluate_expected_result(benchmark: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Adjust ``_all_pass`` when a benchmark is expected to fail gracefully."""
    expected_result = benchmark.get("expected_result", "pass")
    if expected_result != "fail":
        return

    error_msg = result.get("error", "")
    # Require a non-empty error for an expected-fail benchmark. The previous
    # default ".*" matched the empty string, so a negative test the skill
    # accidentally satisfied (no error) was reported as PASS.
    expected_error = benchmark.get("expected_error", ".+")
    matched = bool(re.search(expected_error, error_msg, re.DOTALL))
    result["_expected_result"] = "fail"
    result["_expected_error_matched"] = matched
    result["_all_pass"] = matched


def _format_benchmark_results(results: Dict[str, Any], fmt: str) -> str:
    """Serialize benchmark results to yaml, json, or markdown."""
    fmt = fmt.lower()
    if fmt == "json":
        return json.dumps(results, indent=2, ensure_ascii=False)
    if fmt == "yaml":
        return cast(str, yaml.safe_dump(results, allow_unicode=True, sort_keys=False))
    if fmt == "markdown":
        lines = ["# Benchmark Results\n", f"- Skill: `{results.get('skill')}`", ""]
        lines.append("| Benchmark | Status | Notes |")
        lines.append("|---|---|---|")
        for bench_id, bench in results.get("benchmarks", {}).items():
            status = "PASS" if bench.get("_all_pass") else "FAIL"
            notes = ""
            if "error" in bench:
                notes = bench["error"]
            elif "_expected_result" in bench:
                notes = f"expected {bench['_expected_result']}"
            lines.append(f"| {bench_id} | {status} | {notes} |")
        lines.append("")
        lines.append(f"- Overall: {'PASS' if results.get('_all_pass') else 'FAIL'}")
        return "\n".join(lines)
    raise ValueError(f"Unsupported output format: {fmt!r}")


def run_benchmarks(
    skill: str,
    registry_path: Path,
    code_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    suite: Optional[str] = None,
    level: Optional[int] = None,
    task: Optional[str] = None,
    output_format: str = "yaml",
    gpu: Optional[bool] = None,
    skill_dir: Optional[Path] = None,
    verify_only: bool = False,
    agent_command: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run all benchmarks for a skill and return results."""
    registry_path = registry_path.resolve()
    registry = load_registry(registry_path)
    registry_dir = registry_path.parent

    # Load any plugins declared in the registry under ``plugins`` so they are
    # available for task dispatch in run_single_benchmark.
    from .plugins import load_registry_plugins

    load_registry_plugins(registry)

    raw_benchmarks = registry.get("benchmarks", {})
    selected_ids = _filter_benchmarks(raw_benchmarks, suite, level, registry)

    benchmarks: List[Dict[str, Any]] = []
    for bid in selected_ids:
        b = raw_benchmarks.get(bid)
        if b is None:
            raise ValueError(f"Suite references unknown benchmark: {bid!r}")
        b["_id"] = bid
        # Match by explicit skill field or legacy skills list.
        # `or []` guards against `skills: null` in YAML (None is not iterable).
        if b.get("skill") == skill or skill in (b.get("skills") or []):
            benchmarks.append(b)

    if task is not None:
        benchmarks = [b for b in benchmarks if b.get("task") == task]

    # Filter out GPU-only benchmarks when no GPU is available.
    has_gpu = gpu if gpu is not None else _has_gpu()
    if not has_gpu:
        skipped = [b for b in benchmarks if b.get("requires_gpu")]
        benchmarks = [b for b in benchmarks if not b.get("requires_gpu")]
        for b in skipped:
            print(f"[SKIP] {b['name']}: requires GPU")

    label_parts = [f"skill: {skill}"]
    if suite:
        label_parts.append(f"suite: {suite}")
    if level:
        label_parts.append(f"level: {level}")
    if verify_only:
        label_parts.append("verify-only")
    print(f"Running {len(benchmarks)} benchmarks ({', '.join(label_parts)})\n")

    all_pass = True
    overall: Dict[str, Any] = {"skill": skill, "benchmarks": {}}

    for b in benchmarks:
        result = run_single_benchmark(
            b,
            skill,
            code_path,
            registry,
            registry_dir,
            verify_only=verify_only,
            agent_command=agent_command,
        )
        _evaluate_expected_result(b, result)
        result["_real_data"] = bool(b.get("real_data"))
        status = "PASS" if result.get("_all_pass") else "FAIL"
        print(f"[{status}] {b['name']}: {result}")
        overall["benchmarks"][b["_id"]] = result
        if not result.get("_all_pass"):
            all_pass = False

    overall["_all_pass"] = all_pass
    overall["_suite"] = suite
    overall["_level"] = level

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_format_benchmark_results(overall, output_format), encoding="utf-8")
        print(f"\nResults written to {output_path}")

    return overall


def main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmarks for a skill.")
    parser.add_argument(
        "--registry",
        default="benchmark_registry.yaml",
        help="Benchmark registry YAML (per-skill: benchmarks/<skill>/registry.yaml)",
    )
    parser.add_argument("--skill", required=True, help="Skill name")
    parser.add_argument(
        "--code", help="Path to generated skill code to execute (omit to verify existing output)"
    )
    parser.add_argument("--output", help="Output results file")
    parser.add_argument(
        "--suite",
        help="Run only benchmarks in the named suite (defined in registry)",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=[0, 1, 2, 3],
        help="Run only benchmarks with the given level (0=unit, 1=component, 2=integration, 3=release)",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Assume GPU is available (skip GPU requirement checks)",
    )
    parser.add_argument(
        "--output-format",
        choices=["yaml", "json", "markdown"],
        default="yaml",
        help="Output format for results",
    )
    args = parser.parse_args()

    results = run_benchmarks(
        args.skill,
        Path(args.registry),
        Path(args.code) if args.code else None,
        Path(args.output) if args.output else None,
        suite=args.suite,
        level=args.level,
        output_format=args.output_format,
        gpu=args.gpu,
    )
    return 0 if results.get("_all_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
