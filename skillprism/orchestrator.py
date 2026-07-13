#!/usr/bin/env python3
"""
Skill quality pipeline: tie evaluation, testing, and improvement into a single
measurement workflow.

Usage:
    skill-pipeline --intent "evaluate all skills" --skills-dir ./skills
    skill-pipeline --intent "run tests" --skills-dir ./skills --benchmark-registry ./benchmarks/<skill>/registry.yaml
    skill-pipeline --intent "run full quality pipeline" --skills-dir ./skills --benchmark-registry ./benchmarks/<skill>/registry.yaml
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import yaml

from .benchmark.regression import compare_benchmark_results, load_yaml
from .benchmark.runner import run_benchmarks
from .evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    SkillReport,
    detect_skill_type,
    evaluate_skill,
    format_scorecard,
    get_weights,
    load_config,
)
from .gradual import run_gradual_pipeline


def _find_command(cli_name: str, wrapper_name: str, engine_dir: Path) -> List[str]:
    """Prefer installed CLI, fall back to repo wrapper."""
    if shutil.which(cli_name):
        return [cli_name]
    wrapper = engine_dir / wrapper_name
    if wrapper.exists():
        return [sys.executable, str(wrapper)]
    print(f"Error: neither `{cli_name}` CLI nor `{wrapper}` found.")
    sys.exit(2)


def _run(cmd: List[str]) -> int:
    """Run a subprocess command; raise on non-zero exit.

    Previously the return code was returned and never checked by callers, so a
    crashed ``evaluate-skill`` / ``improve-skill`` subprocess silently produced
    a stale baseline or empty scorecard while the orchestrator continued.
    """
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed (exit {result.returncode}): {' '.join(cmd)}")
    return result.returncode


def run_rubric_all(
    skills_dir: Path,
    engine_dir: Path,
    config_path: Path,
    output: Path,
    run_smoke: bool = False,
) -> List[SkillReport]:
    """Run rubric on all skills and return reports.

    Runs the rubric **once**, in-process, for each skill — the resulting
    ``SkillReport`` objects feed downstream (worst-skill selection) and the
    scorecard file is written from those same reports. Previously the rubric
    was run twice (CLI subprocess + in-process) with the CLI result discarded.
    """
    config = load_config(config_path)
    reports: List[SkillReport] = []
    for skill_path in sorted(
        p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    ):
        reports.append(evaluate_skill(skill_path, config, run_smoke=run_smoke))

    try:
        output.write_text(format_scorecard(reports, config), encoding="utf-8")
    except OSError as exc:
        print(f"Warning: could not write scorecard to {output}: {exc}")
    return reports


def _get_skill_type(skill_path: Path, config: Dict[str, Any]) -> Optional[str]:
    """Detect skill type using the same logic as the rubric evaluator."""
    try:
        return cast(Optional[str], detect_skill_type(skill_path, config))
    except Exception:
        return None


def run_benchmark_for_skill(
    skill_name: str,
    skill_type: str,
    registry_path: Path,
    skills_dir: Path,
    output_dir: Path,
    baseline_dir: Optional[Path] = None,
    suite: Optional[str] = None,
) -> Dict[str, Any]:
    """Run benchmark for a single skill and optionally compare to baseline."""
    if not registry_path.exists():
        print(f"Benchmark registry not found: {registry_path}")
        return {"error": "registry not found"}

    # Try to find skill-generated code
    skill_path = skills_dir / skill_name
    candidate = skill_path / "examples" / "minimal_example.py"
    code_path: Optional[Path] = candidate if candidate.exists() else None

    latest_output = output_dir / f"{skill_name}.yaml"
    results = run_benchmarks(skill_type, registry_path, code_path, latest_output, suite=suite)

    # Compare to baseline if available
    if baseline_dir:
        baseline_file = baseline_dir / f"{skill_name}.yaml"
        if baseline_file.exists():
            baseline = load_yaml(baseline_file)
            current = load_yaml(latest_output)
            comparison = compare_benchmark_results(current, baseline, tolerance=0.03)
            results["_regression"] = comparison
            results["_regression_pass"] = comparison["all_pass"]

    return results


def run_benchmarks_all(
    skills_dir: Path,
    registry_path: Path,
    output_dir: Path,
    baseline_dir: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
    suite: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Run benchmarks for all skills whose type appears in the registry."""
    if not registry_path.exists():
        print(f"Benchmark registry not found: {registry_path}")
        return {}

    registry = cast(Dict[str, Any], yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {})
    all_results: Dict[str, Dict[str, Any]] = {}

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect skills that appear in registry (or in the selected suite)
    benchmarked_types: set[str] = set()
    if suite:
        suite_entry = (registry.get("suites") or {}).get(suite, {})
        suite_benchmarks = suite_entry.get("benchmarks", [])
        for bid in suite_benchmarks:
            b = registry.get("benchmarks", {}).get(bid)
            if b:
                if b.get("skill"):
                    benchmarked_types.add(b["skill"])
                benchmarked_types.update(b.get("skills", []))
    else:
        for b in registry.get("benchmarks", {}).values():
            if b.get("skill"):
                benchmarked_types.add(b["skill"])
            benchmarked_types.update(b.get("skills", []))

    for skill_path in sorted(
        p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    ):
        skill_type = _get_skill_type(skill_path, config) if config else None
        if not skill_type or skill_type not in benchmarked_types:
            continue
        print(f"\n### Benchmarking {skill_path.name} (type: {skill_type})")
        all_results[skill_path.name] = run_benchmark_for_skill(
            skill_path.name,
            skill_type,
            registry_path,
            skills_dir,
            output_dir,
            baseline_dir,
            suite=suite,
        )

    return all_results


def run_gradual_for_skill(
    skill_name: str,
    skill_type: str,
    registry_path: Path,
    output_dir: Path,
    max_level: int = 2,
    suite: Optional[str] = None,
    ratchet: bool = True,
    code_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run Gradual pipeline for a single skill."""
    if not registry_path.exists():
        print(f"Benchmark registry not found: {registry_path}")
        return {"error": "registry not found"}

    skill_output_dir = output_dir / skill_name
    return run_gradual_pipeline(
        skill=skill_type,
        registry_path=registry_path,
        suite=suite,
        max_level=max_level,
        base_output_dir=skill_output_dir,
        ratchet=ratchet,
        code_path=code_path,
    )


def run_gradual_all(
    skills_dir: Path,
    registry_path: Path,
    output_dir: Path,
    config: Optional[Dict[str, Any]] = None,
    max_level: int = 2,
    suite: Optional[str] = None,
    ratchet: bool = True,
    code_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Run Gradual pipeline for all skills whose type appears in the registry."""
    if not registry_path.exists():
        print(f"Benchmark registry not found: {registry_path}")
        return {}

    registry = cast(Dict[str, Any], yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {})
    all_results: Dict[str, Dict[str, Any]] = {}
    output_dir.mkdir(parents=True, exist_ok=True)

    benchmarked_types: set[str] = set()
    if suite:
        suite_entry = (registry.get("suites") or {}).get(suite, {})
        suite_benchmarks = suite_entry.get("benchmarks", [])
        for bid in suite_benchmarks:
            b = registry.get("benchmarks", {}).get(bid)
            if b:
                if b.get("skill"):
                    benchmarked_types.add(b["skill"])
                benchmarked_types.update(b.get("skills", []))
    else:
        for b in registry.get("benchmarks", {}).values():
            if b.get("skill"):
                benchmarked_types.add(b["skill"])
            benchmarked_types.update(b.get("skills", []))

    for skill_path in sorted(
        p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    ):
        skill_type = _get_skill_type(skill_path, config) if config else None
        if not skill_type or skill_type not in benchmarked_types:
            continue
        print(f"\n### Gradual pipeline for {skill_path.name} (type: {skill_type})")
        all_results[skill_path.name] = run_gradual_for_skill(
            skill_path.name,
            skill_type,
            registry_path,
            output_dir,
            max_level=max_level,
            suite=suite,
            ratchet=ratchet,
            code_path=code_path,
        )

    return all_results


def find_worst_skill(reports: List[SkillReport], config: Dict[str, Any]) -> Optional[SkillReport]:
    """Find the skill with the lowest score."""
    if not reports:
        return None
    weights = get_weights(config)
    return min(reports, key=lambda r: r.fused_score(weights))


def generate_combined_report(
    rubric_output: Path,
    benchmark_results: Dict[str, Dict[str, Any]],
    worst_skill: Optional[SkillReport],
    output_path: Path,
    optimize_next_command: Optional[str] = None,
) -> None:
    """Generate a Markdown report combining rubric scorecard, benchmark results, and optimization recommendation."""
    lines: List[str] = ["# Skill Quality Pipeline Report\n"]

    if rubric_output.exists():
        lines.append(rubric_output.read_text(encoding="utf-8"))
        lines.append("\n---\n")

    lines.append("## Benchmark Results\n")
    if not benchmark_results:
        lines.append("No benchmarks run.\n")
    else:
        lines.append("| Skill | Benchmark | Status | Notes |")
        lines.append("|---|---|---|---|")
        for skill, results in benchmark_results.items():
            for bench_id, bench_result in results.get("benchmarks", {}).items():
                status = "PASS" if bench_result.get("_all_pass") else "FAIL"
                notes = ""
                if "_regression_pass" in results:
                    notes = (
                        "regression: PASS" if results["_regression_pass"] else "regression: FAIL"
                    )
                lines.append(f"| {skill} | {bench_id} | {status} | {notes} |")
        lines.append("")

    if worst_skill:
        lines.append("## Optimization Recommendation\n")
        lines.append(f"Lowest-scoring skill: `{worst_skill.name}` ({worst_skill.skill_type})\n")
        if optimize_next_command:
            lines.append(f"Next step: edit `{worst_skill.name}/SKILL.md` and then run:")
            lines.append(f"\n```bash\n{optimize_next_command}\n```\n")
        else:
            lines.append("Next step: use `improve-skill` to iteratively edit its SKILL.md.")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nCombined report written to {output_path}")


def run_optimize_setup(
    worst: SkillReport,
    skills_dir: Path,
    engine_dir: Path,
    config_path: Path,
    benchmark_registry: Optional[Path] = None,
) -> str:
    """Record baseline for the worst skill and return the next judge command."""
    skill_path = skills_dir / worst.name
    cmd = _find_command("improve-skill", "optimize_skill.py", engine_dir)
    record_cmd = cmd + [
        str(skill_path),
        "--record-baseline",
        "--config",
        str(config_path),
    ]
    if benchmark_registry:
        record_cmd.extend(["--benchmark-registry", str(benchmark_registry)])
    _run(record_cmd)

    suggest_cmd = cmd + [
        str(skill_path),
        "--suggest",
        "--config",
        str(config_path),
    ]
    _run(suggest_cmd)

    next_cmd_parts = cmd + [
        str(skill_path),
        "--judge",
        "--config",
        str(config_path),
    ]
    if benchmark_registry:
        next_cmd_parts.extend(["--benchmark-registry", str(benchmark_registry)])
    return " ".join(next_cmd_parts)


def _build_pipeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Skill quality orchestrator.")
    parser.add_argument("--intent", required=True, help="High-level intent")
    parser.add_argument("--skills-dir", default="./skills", help="Directory containing skills")
    parser.add_argument(
        "--engine-dir", default=".", help="Directory containing engine entry scripts"
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG), help="Path to skill_rubric_types.yaml"
    )
    parser.add_argument("--benchmark-registry", help="Path to benchmark registry YAML")
    parser.add_argument(
        "--benchmark-suite",
        help="Run only benchmarks in the named suite",
    )
    parser.add_argument(
        "--benchmark-output-dir",
        default="./benchmarks/latest",
        help="Directory for benchmark outputs",
    )
    parser.add_argument(
        "--benchmark-baseline-dir",
        default="./benchmarks/baselines",
        help="Directory for benchmark baselines",
    )
    parser.add_argument(
        "--output", default="reports/SKILL_QUALITY_REPORT.md", help="Combined report output path"
    )
    parser.add_argument("--run-smoke", action="store_true")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Auto-apply optimization decisions (requires --intent optimize)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Max optimization rounds (requires --intent optimize)",
    )
    parser.add_argument(
        "--max-level",
        type=int,
        choices=[0, 1, 2, 3],
        default=2,
        help="Max gradual level (requires --intent gradual)",
    )
    parser.add_argument(
        "--no-ratchet",
        action="store_true",
        help="Do not ratchet gradual baselines forward",
    )
    return parser


def _dispatch_evaluate(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Evaluate only: run rubric and generate a combined report."""
    skills_dir = Path(args.skills_dir)
    engine_dir = Path(args.engine_dir)
    config_path = Path(args.config)
    rubric_output = Path(args.output).with_name("_rubric_scorecard.md")
    run_rubric_all(skills_dir, engine_dir, config_path, rubric_output, args.run_smoke)
    generate_combined_report(rubric_output, {}, None, Path(args.output))
    return 0


def _dispatch_gradual(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Run the gradual failure-mode-first pipeline."""
    if not args.benchmark_registry:
        print("Error: --benchmark-registry required for gradual intents")
        return 2
    skills_dir = Path(args.skills_dir)
    registry_path = Path(args.benchmark_registry)
    output_dir = Path(args.benchmark_output_dir) / "gradual"
    results = run_gradual_all(
        skills_dir,
        registry_path,
        output_dir,
        config,
        max_level=args.max_level,
        suite=args.benchmark_suite,
        ratchet=not args.no_ratchet,
    )
    all_pass = all(r.get("_all_pass") for r in results.values())
    return 0 if all_pass else 1


def _dispatch_benchmarks(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Run benchmarks only and check pass/fail."""
    if not args.benchmark_registry:
        print("Error: --benchmark-registry required for benchmark intents")
        return 2
    skills_dir = Path(args.skills_dir)
    registry_path = Path(args.benchmark_registry)
    output_dir = Path(args.benchmark_output_dir)
    baseline_dir = Path(args.benchmark_baseline_dir)
    results = run_benchmarks_all(
        skills_dir, registry_path, output_dir, baseline_dir, config, suite=args.benchmark_suite
    )
    all_pass = all(r.get("_all_pass") for r in results.values())
    return 0 if all_pass else 1


def _dispatch_optimize(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Optimize: evaluate, benchmark, identify worst skill, and set up next steps."""
    skills_dir = Path(args.skills_dir)
    engine_dir = Path(args.engine_dir)
    config_path = Path(args.config)

    print("=== Stage 1: Rubric Evaluation ===")
    rubric_output = Path(args.output).with_name("_rubric_scorecard.md")
    reports = run_rubric_all(skills_dir, engine_dir, config_path, rubric_output, args.run_smoke)

    benchmark_results: Dict[str, Dict[str, Any]] = {}
    if args.benchmark_registry:
        print("\n=== Stage 2: Benchmark Tests ===")
        registry_path = Path(args.benchmark_registry)
        output_dir = Path(args.benchmark_output_dir)
        baseline_dir = Path(args.benchmark_baseline_dir)
        benchmark_results = run_benchmarks_all(
            skills_dir,
            registry_path,
            output_dir,
            baseline_dir,
            config,
            suite=args.benchmark_suite,
        )

    print("\n=== Stage 3: Identify Worst Skill ===")
    worst = find_worst_skill(reports, config)
    if not worst:
        print("No skills found")
        generate_combined_report(rubric_output, benchmark_results, None, Path(args.output))
        return 0

    weights = get_weights(config)
    print(f"Worst skill: {worst.name} (score {worst.fused_score(weights):.1f})")

    print("\n=== Stage 4: Setup Optimization ===")
    next_cmd = run_optimize_setup(
        worst,
        skills_dir,
        engine_dir,
        config_path,
        benchmark_registry=Path(args.benchmark_registry) if args.benchmark_registry else None,
    )
    generate_combined_report(
        rubric_output,
        benchmark_results,
        worst,
        Path(args.output),
        optimize_next_command=next_cmd,
    )
    print(f"\nNext: edit {worst.name}/SKILL.md, then run:\n  {next_cmd}")
    print(
        "Or configure SKILLPRISM_EDITOR_COMMAND and run:\n"
        f"  improve-skill {skills_dir / worst.name} --auto-edit --apply"
    )
    return 0


def _dispatch_full_pipeline(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """Full pipeline: rubric + benchmark + identify worst skill."""
    skills_dir = Path(args.skills_dir)
    engine_dir = Path(args.engine_dir)
    config_path = Path(args.config)

    print("=== Stage 1: Rubric Evaluation ===")
    rubric_output = Path(args.output).with_name("_rubric_scorecard.md")
    reports = run_rubric_all(skills_dir, engine_dir, config_path, rubric_output, args.run_smoke)

    benchmark_results: Dict[str, Dict[str, Any]] = {}
    if args.benchmark_registry:
        print("\n=== Stage 2: Benchmark Tests ===")
        registry_path = Path(args.benchmark_registry)
        output_dir = Path(args.benchmark_output_dir)
        baseline_dir = Path(args.benchmark_baseline_dir)
        benchmark_results = run_benchmarks_all(
            skills_dir,
            registry_path,
            output_dir,
            baseline_dir,
            config,
            suite=args.benchmark_suite,
        )

    print("\n=== Stage 3: Identify Worst Skill ===")
    worst = find_worst_skill(reports, config)
    if worst:
        weights = get_weights(config)
        print(f"Worst skill: {worst.name} (score {worst.fused_score(weights):.1f})")
    else:
        print("No skills found")

    generate_combined_report(rubric_output, benchmark_results, worst, Path(args.output))
    return 0


def main() -> int:
    parser = _build_pipeline_parser()
    args = parser.parse_args()
    config = load_config(Path(args.config))
    intent_lower = args.intent.lower()

    if (
        any(k in intent_lower for k in ["evaluate", "eval", "评分", "评估", "打分"])
        and "pipeline" not in intent_lower
        and "optimize" not in intent_lower
    ):
        return _dispatch_evaluate(args, config)

    if any(k in intent_lower for k in ["gradual", "渐进"]):
        return _dispatch_gradual(args, config)

    if (
        "benchmark" in intent_lower
        and "pipeline" not in intent_lower
        and "optimize" not in intent_lower
    ):
        return _dispatch_benchmarks(args, config)

    if any(k in intent_lower for k in ["optimize", "improve", "优化", "提升"]):
        return _dispatch_optimize(args, config)

    return _dispatch_full_pipeline(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
