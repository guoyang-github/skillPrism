#!/usr/bin/env python3
"""Command-line entry point for the skillPrism CI pipeline.

The CI pipeline runs deterministic, objective checks by default:

- Rubric static evaluation
- Smoke tests
- Dependency reproducibility checks
- Security scanning

Dynamic benchmarks are optional and require a pre-generated code artifact
(``--code``). The CI pipeline does NOT call LLMs to generate code.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from skillprism.ci.pipeline import run_ci_pipeline
from skillprism.ci.reports import format_report, write_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run skillPrism CI gate (static checks by default; no LLM calls)."
    )
    parser.add_argument(
        "--registry",
        default="benchmark_registry.yaml",
        help="Benchmark registry YAML (per-skill: benchmarks/<skill>/registry.yaml)",
    )
    parser.add_argument("--skill", required=True, help="Skill name or path")
    parser.add_argument(
        "--baseline",
        help="Path to baseline results YAML for regression comparison",
    )
    parser.add_argument(
        "--output-dir",
        default="ci-output",
        help="Directory for CI artifacts",
    )
    parser.add_argument(
        "--config",
        help="Path to skill_rubric_types.yaml (default: bundled config)",
    )
    parser.add_argument(
        "--suite",
        help="Run only benchmarks in the named suite",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=[0, 1, 2, 3],
        help="Run only benchmarks with the given level",
    )
    parser.add_argument(
        "--run-benchmark",
        action="store_true",
        help="Also run dynamic benchmarks (requires --code)",
    )
    parser.add_argument(
        "--code",
        help="Path to pre-generated skill code (required for --run-benchmark)",
    )
    parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="Skip smoke tests",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="Skip dependency reproducibility checks",
    )
    parser.add_argument(
        "--deps-dry-run",
        action="store_true",
        help="Run pip/conda dry-run dependency installs (slow)",
    )
    parser.add_argument(
        "--ratchet",
        action="store_true",
        help="Update benchmark baseline to current results if all checks pass",
    )
    parser.add_argument(
        "--no-stop-on-regression",
        action="store_true",
        help="Do NOT fail the pipeline on benchmark regression (default: regressions fail CI)",
    )
    parser.add_argument(
        "--output-format",
        choices=["yaml", "json", "markdown"],
        default="markdown",
        help="Report output format",
    )
    args = parser.parse_args()

    if args.run_benchmark and not args.code:
        print(
            "Warning: --run-benchmark without --code. Benchmarks that require generated code will use pass-through or fail. CI does not generate code via LLM.",
            file=__import__("sys").stderr,
        )

    results = run_ci_pipeline(
        skill=args.skill,
        registry_path=Path(args.registry),
        baseline_path=Path(args.baseline) if args.baseline else None,
        output_dir=Path(args.output_dir),
        config_path=Path(args.config) if args.config else None,
        suite=args.suite,
        level=args.level,
        ratchet=args.ratchet,
        stop_on_regression=not args.no_stop_on_regression,
        output_format=args.output_format if args.output_format in ("yaml", "markdown") else "json",
        static_only=not args.run_benchmark,
        run_benchmark=args.run_benchmark,
        run_smoke=not args.no_smoke,
        run_deps=not args.no_deps,
        run_deps_dry_run=args.deps_dry_run,
        code_path=Path(args.code) if args.code else None,
        verify_only=not args.run_benchmark,
    )

    report = format_report(results, args.output_format)
    report_path = Path(args.output_dir) / f"report.{args.output_format}"
    write_report(report, report_path)
    print(report)
    print(f"\nReport written to {report_path}")

    return 0 if results.get("_all_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
