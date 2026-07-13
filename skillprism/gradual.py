#!/usr/bin/env python3
"""Gradual (failure-mode-first) test pipeline for skillPrism.

The gradual pipeline is designed for long-running, computationally expensive
skills such as spatial transcriptomics models. Instead of testing against the
full benchmark suite, it starts with the cheapest failure-prone cases
(level 0 unit and boundary tests), ratchets the baseline forward only when they
pass, then progresses to integration (level 2) and finally real-data release
(level 3) benchmarks. This catches regressions early and avoids wasting GPU time
on obviously broken edits.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from skillprism.ci.pipeline import CIPipeline

LEVEL_NAMES = {
    0: "unit",
    1: "component",
    2: "integration",
    3: "release",
}


def _default_baseline_path(
    skill_path: Path, level: int, suite: Optional[str], output_dir: Optional[Path] = None
) -> Path:
    """Default stage baseline path.

    Baselines live under ``<output_dir>/.baselines/<skill>/...`` rather than
    inside the skill source tree (previously ``<skill>/.skillprism_baseline/``),
    which polluted the checked-out skill repo with generated ratchet artifacts
    on every gradual run.
    """
    name = f"gradual_baseline_level{level}"
    if suite:
        name += f"_{suite}"
    base = output_dir or Path("ci-output") / "gradual"
    return base / ".baselines" / skill_path.name / f"{name}.yaml"


def run_gradual_stage(
    skill: str,
    registry_path: Path,
    level: int,
    suite: Optional[str] = None,
    baseline_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    ratchet: bool = True,
    code_path: Optional[Path] = None,
    results_mode: bool = True,
    agent_command: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run a single Gradual stage and compare against the stage baseline."""
    output_dir = output_dir or Path("ci-output") / "gradual"
    stage_output_dir = output_dir / f"level{level}"

    pipeline = CIPipeline(
        skill=skill,
        registry_path=registry_path,
        baseline_path=baseline_path,
        output_dir=stage_output_dir,
    )
    return pipeline.run(
        level=level,
        suite=suite,
        ratchet=ratchet,
        stop_on_regression=True,
        output_format="yaml",
        static_only=False,
        run_benchmark=True,
        code_path=code_path,
        results_mode=results_mode,
        agent_command=agent_command,
    )


def run_gradual_pipeline(
    skill: str,
    registry_path: Path,
    suite: Optional[str] = None,
    max_level: int = 3,
    base_output_dir: Optional[Path] = None,
    ratchet: bool = True,
    code_path: Optional[Path] = None,
    results_mode: bool = True,
    agent_command: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run Gradual stages from level 0 up to ``max_level``.

    Each stage runs its benchmarks, compares to the per-stage baseline, and
    ratchets the baseline forward if the stage passes. If a stage fails, the
    pipeline stops immediately so the agent can fix the Skill before expensive
    later stages.
    """
    if max_level < 0 or max_level > 3:
        raise ValueError("max_level must be between 0 and 3")

    base_output_dir = base_output_dir or Path("ci-output") / "gradual"
    overall: Dict[str, Any] = {
        "skill": skill,
        "suite": suite,
        "max_level": max_level,
        "stages": {},
        "_all_pass": True,
    }

    for level in range(max_level + 1):
        print(f"\n=== Gradual test stage {level}: {LEVEL_NAMES[level]} ===")
        baseline_path = _default_baseline_path(Path(skill), level, suite, base_output_dir)
        stage_result = run_gradual_stage(
            skill=skill,
            registry_path=registry_path,
            level=level,
            suite=suite,
            baseline_path=baseline_path,
            output_dir=base_output_dir,
            ratchet=ratchet,
            code_path=code_path,
            results_mode=results_mode,
            agent_command=agent_command,
        )
        overall["stages"][f"level{level}"] = stage_result
        if not stage_result.get("_all_pass"):
            overall["_all_pass"] = False
            print(f"Gradual stage {level} failed. Stopping pipeline.")
            break
        print(f"Gradual stage {level} passed.")

    return overall


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the gradual (failure-mode-first) test pipeline for a skill."
    )
    parser.add_argument("--skill", required=True, help="Skill name")
    parser.add_argument(
        "--registry",
        default="benchmark_registry.yaml",
        help="Benchmark registry YAML (per-skill: benchmarks/<skill>/registry.yaml)",
    )
    parser.add_argument(
        "--suite",
        help="Run only benchmarks in the named suite (applied at every stage)",
    )
    parser.add_argument(
        "--max-level",
        type=int,
        choices=[0, 1, 2, 3],
        default=3,
        help="Highest Gradual stage to run (default: 3)",
    )
    parser.add_argument(
        "--output-dir",
        default="ci-output/gradual",
        help="Directory for Gradual stage artifacts",
    )
    parser.add_argument(
        "--no-ratchet",
        action="store_true",
        help="Do not update per-stage baselines",
    )
    parser.add_argument(
        "--code",
        help="Path to generated skill code to execute",
    )
    parser.add_argument(
        "--results",
        dest="results_mode",
        action="store_true",
        default=None,
        help="Skip execution; evaluate the existing results at the expected output path "
        "(default: True). Explicit --results ignores SKILLPRISM_AGENT_COMMAND.",
    )
    args = parser.parse_args()

    code_path = Path(args.code) if args.code else None
    agent_command = None
    if code_path is not None:
        if not code_path.exists():
            print(f"Error: code file not found: {code_path}")
            return 2
        if args.results_mode is True:
            print("Error: --results cannot be used with --code")
            return 2
        results_mode = False
    elif args.results_mode is True:
        results_mode = True
    elif os.environ.get("SKILLPRISM_AGENT_COMMAND"):
        results_mode = False
        agent_command = os.environ["SKILLPRISM_AGENT_COMMAND"].split()
    else:
        results_mode = True

    overall = run_gradual_pipeline(
        skill=args.skill,
        registry_path=Path(args.registry),
        suite=args.suite,
        max_level=args.max_level,
        base_output_dir=Path(args.output_dir),
        ratchet=not args.no_ratchet,
        code_path=code_path,
        results_mode=results_mode,
        agent_command=agent_command,
    )

    print("\n=== Gradual test pipeline summary ===")
    for stage_name, stage_result in overall["stages"].items():
        status = "PASS" if stage_result.get("_all_pass") else "FAIL"
        print(f"  {stage_name}: {status}")
    print(f"\nOverall: {'PASS' if overall['_all_pass'] else 'FAIL'}")

    return 0 if overall["_all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
