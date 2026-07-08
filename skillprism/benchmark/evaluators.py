#!/usr/bin/env python3
"""Generic benchmark evaluator: resolves metric functions and checks criteria."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .metrics import get_metric, metric_passes


class GenericEvaluator:
    """Evaluate a benchmark output by calling registered metric functions."""

    def evaluate(
        self,
        actual_path: Path,
        expected_path: Optional[Path],
        metrics_spec: List[Dict[str, Any]],
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute each metric in ``metrics_spec`` and check its criteria."""
        results: Dict[str, Any] = {}
        passed: Dict[str, bool] = {}

        for metric in metrics_spec:
            metric_id = metric["id"]
            compute_fn = get_metric(metric_id)
            if compute_fn is None:
                results[metric_id] = None
                passed[metric_id] = False
                continue

            try:
                value = compute_fn(actual_path, expected_path, task_spec)
            except Exception as exc:
                results[metric_id] = f"error: {exc}"
                passed[metric_id] = False
                continue

            results[metric_id] = value
            if value is None:
                passed[metric_id] = False
                continue
            passed[metric_id] = metric_passes(value, metric)

        results["_metric_pass"] = passed
        results["_all_pass"] = all(passed.values())
        return results


def get_evaluator(task_spec: Dict[str, Any]) -> GenericEvaluator:
    """Return the generic evaluator (output format is no longer used for selection)."""
    return GenericEvaluator()
