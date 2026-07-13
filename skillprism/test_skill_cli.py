#!/usr/bin/env python3
"""Unified `test-skill` CLI.

Provides a single user-facing command for all skill testing needs:

- ``test-skill --skill <name> --task <task>``: verify that the Agent has
  already produced the expected output (results mode by default). If
  ``SKILLPRISM_AGENT_COMMAND`` is set, the engine invokes that external agent
  instead.
- ``test-skill --skill <name> --task <task> --code <path>``: execute the
  provided code and evaluate the produced output.
- ``test-skill --skill <name> --registry <path>``: run all benchmarks for the
  skill from the registry.

The engine does not call LLMs directly unless an external agent command is
configured via ``SKILLPRISM_AGENT_COMMAND``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .benchmark.runner import _format_benchmark_results, run_benchmarks
from .gradual import run_gradual_pipeline
from .test_prompts import artifacts_dir


def _run_single(
    skill: str,
    code_path: Optional[Path],
    registry_path: Path,
    task: Optional[str],
    level: Optional[int],
    suite: Optional[str],
    gpu: Optional[bool],
    results_mode: bool = False,
    agent_command: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
    output_format: str = "yaml",
) -> Dict[str, Any]:
    """Run benchmarks in single mode and optionally write results to disk."""
    return run_benchmarks(
        skill=skill,
        registry_path=registry_path,
        code_path=code_path,
        level=level,
        suite=suite,
        task=task,
        gpu=gpu,
        results_mode=results_mode,
        agent_command=agent_command,
        output_path=output_path,
        output_format=output_format,
    )


def _run_gradual(
    skill: str,
    code_path: Optional[Path],
    registry_path: Path,
    max_level: int,
    suite: Optional[str],
    output_dir: Path,
    ratchet: bool,
    gpu: Optional[bool],
    results_mode: bool = True,
    agent_command: Optional[List[str]] = None,
) -> Dict[str, Any]:
    # run_gradual_pipeline takes the skill and registry path. The code is
    # executed inside each benchmark via run_benchmarks when provided.
    return run_gradual_pipeline(
        skill=skill,
        registry_path=registry_path,
        suite=suite,
        max_level=max_level,
        base_output_dir=output_dir,
        ratchet=ratchet,
        code_path=code_path,
        results_mode=results_mode,
        agent_command=agent_command,
    )


def _run_quick(
    skill: str,
    code_path: Optional[Path],
    registry_path: Path,
    suite: Optional[str],
    gpu: Optional[bool],
    results_mode: bool = True,
    agent_command: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run level 0 then level 1; fail fast."""
    level0 = _run_single(
        skill,
        code_path,
        registry_path,
        task=None,
        level=0,
        suite=suite,
        gpu=gpu,
        results_mode=results_mode,
        agent_command=agent_command,
    )
    if not level0.get("_all_pass"):
        return {
            "skill": skill,
            "mode": "quick",
            "level0": level0,
            "_all_pass": False,
        }
    level1 = _run_single(
        skill,
        code_path,
        registry_path,
        task=None,
        level=1,
        suite=suite,
        gpu=gpu,
        results_mode=results_mode,
        agent_command=agent_command,
    )
    return {
        "skill": skill,
        "mode": "quick",
        "level0": level0,
        "level1": level1,
        "_all_pass": level1.get("_all_pass", False),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test a skill against benchmarks.")
    parser.add_argument("--skill", required=True, help="Skill name")
    parser.add_argument(
        "--code",
        help="Path to generated skill code to execute",
    )
    parser.add_argument(
        "--task",
        help="Task id to run (uses matching benchmarks in the registry)",
    )
    parser.add_argument(
        "--registry",
        default="benchmark_registry.yaml",
        help="Benchmark registry YAML (per-skill: benchmarks/<skill>/registry.yaml)",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "gradual", "quick"],
        default="single",
        help="Testing mode (default: single)",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=[0, 1, 2, 3],
        help="Benchmark level to run (single mode only)",
    )
    parser.add_argument(
        "--max-level",
        type=int,
        choices=[0, 1, 2, 3],
        default=3,
        help="Highest level for gradual mode (default: 3)",
    )
    parser.add_argument("--suite", help="Run only benchmarks in the named suite")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for test artifacts (default: artifacts/<skill>/ci/test)",
    )
    parser.add_argument(
        "--output",
        help="Write the full results to this file (single mode only)",
    )
    parser.add_argument(
        "--output-format",
        choices=["yaml", "json", "markdown"],
        default="yaml",
        help="Output format when --output is used (default: yaml)",
    )
    parser.add_argument(
        "--no-ratchet",
        action="store_true",
        help="Do not update per-stage baselines (gradual mode only)",
    )
    parser.add_argument(
        "--gpu",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Run GPU-only benchmarks (default: auto-detect)",
    )
    parser.add_argument(
        "--results",
        dest="results_mode",
        action="store_true",
        default=None,
        help="Skip execution; evaluate the existing results at the expected output path "
        "(default: True). Explicit --results ignores SKILLPRISM_AGENT_COMMAND.",
    )
    return parser


def resolve_args(args: argparse.Namespace) -> int:
    """Resolve execution mode from --code, --results, and SKILLPRISM_AGENT_COMMAND.

    Returns 0 on success or a non-zero exit code when arguments conflict.
    """
    if args.code:
        code_path = Path(args.code)
        if not code_path.exists():
            print(f"Error: code file not found: {code_path}")
            return 2
        if args.results_mode is True:
            print("Error: --results cannot be used with --code")
            return 2
        args.results_mode = False
        return 0

    if args.results_mode is True:
        return 0

    # If an external agent command is configured and the user did not ask for
    # results, let the engine invoke the agent.
    if os.environ.get("SKILLPRISM_AGENT_COMMAND"):
        args.results_mode = False
        return 0

    if args.results_mode is None:
        args.results_mode = True
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    skill = args.skill
    code_path = Path(args.code) if args.code else None

    rc = resolve_args(args)
    if rc != 0:
        return rc

    agent_command = None
    if not args.results_mode and not args.code:
        cmd = os.environ.get("SKILLPRISM_AGENT_COMMAND")
        if cmd:
            agent_command = cmd.split()

    registry_path = Path(args.registry)
    output_dir = (
        Path(args.output_dir) if args.output_dir else artifacts_dir(Path(skill)) / "ci" / "test"
    )

    if args.mode == "single":
        if args.level is not None and args.max_level != 3:
            print("Warning: --max-level is ignored in single mode.")
        results = _run_single(
            skill=skill,
            code_path=code_path,
            registry_path=registry_path,
            task=args.task,
            level=args.level,
            suite=args.suite,
            gpu=args.gpu,
            results_mode=args.results_mode,
            agent_command=agent_command,
            output_path=Path(args.output) if args.output else None,
            output_format=args.output_format,
        )
    elif args.mode == "gradual":
        if args.level is not None:
            print("Error: --level cannot be used with --mode gradual; use --max-level")
            return 2
        results = _run_gradual(
            skill=skill,
            code_path=code_path,
            registry_path=registry_path,
            max_level=args.max_level,
            suite=args.suite,
            output_dir=output_dir,
            ratchet=not args.no_ratchet,
            gpu=args.gpu,
            results_mode=args.results_mode,
            agent_command=agent_command,
        )
    else:  # quick
        if args.level is not None or args.max_level != 3:
            print("Warning: --level and --max-level are ignored in quick mode.")
        results = _run_quick(
            skill=skill,
            code_path=code_path,
            registry_path=registry_path,
            suite=args.suite,
            gpu=args.gpu,
            results_mode=args.results_mode,
            agent_command=agent_command,
        )

    if args.output and args.mode != "single":
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            _format_benchmark_results(results, args.output_format),
            encoding="utf-8",
        )
        print(f"\nResults written to {output_path}")

    print(f"\nOverall: {'PASS' if results.get('_all_pass') else 'FAIL'}")
    return 0 if results.get("_all_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
