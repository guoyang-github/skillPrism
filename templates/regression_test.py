#!/usr/bin/env python3
"""
Regression test template for Skill iterative optimization.

This script compares the current benchmark results against a stored baseline
and decides whether a Skill modification should be accepted.

Usage:
    python regression_test.py \
        --results benchmarks/latest/bio-single-cell-clustering.yaml \
        --baseline benchmarks/baselines/bio-single-cell-clustering.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from skillprism.benchmark.regression import compare_benchmark_results, load_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare benchmark results against baseline.")
    parser.add_argument("--results", required=True, help="Path to current benchmark results YAML")
    parser.add_argument("--baseline", required=True, help="Path to baseline YAML")
    parser.add_argument(
        "--tolerance", type=float, default=0.03, help="Relative tolerance (default 3%)"
    )
    args = parser.parse_args()

    current = load_yaml(Path(args.results))
    baseline = load_yaml(Path(args.baseline))

    skill = current.get("skill", "unknown")
    print(f"Regression test for: {skill}")
    print(f"Baseline version: {baseline.get('version', 'unknown')}")
    print(f"Current version:  {current.get('version', 'unknown')}\n")

    comparison = compare_benchmark_results(current, baseline, tolerance=args.tolerance)

    for bench_id, bench_comparison in comparison["benchmarks"].items():
        print(f"--- {bench_id} ---")
        if "error" in bench_comparison:
            print(f"  {bench_comparison['error']}")
            continue
        for metric_name, info in bench_comparison["metrics"].items():
            print(
                f"  {metric_name}: {info['status']} "
                f"(current={info['current']}, baseline={info['baseline']}, "
                f"diff={info.get('relative_diff', 'N/A')})"
            )

    print()
    if comparison["all_pass"]:
        print("RESULT: ACCEPT (no regression detected)")
        return 0
    else:
        print("RESULT: REJECT (regression detected)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
