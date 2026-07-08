#!/usr/bin/env python3
"""P1-7/P1-8/P1-9: judge wrapper, orchestrator, and benchmark-correctness fixes."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from skillprism.benchmark.metrics import _label_column, metric_passes
from skillprism.orchestrator import _run

# --------------------------- P1-9: metric_passes None guard ---------------- #


def test_metric_passes_none_returns_false_not_typeerror() -> None:
    """A None compute value (missing expected/X_pca) must fail, not raise."""
    spec = {"type": "min", "threshold": 0.5}
    assert metric_passes(None, spec) is False


def test_metric_passes_none_max() -> None:
    assert metric_passes(None, {"type": "max", "threshold": 0.5}) is False


# --------------------------- P1-9: label_column --------------------------- #


def test_label_column_defaults_to_leiden() -> None:
    assert _label_column({}) == "leiden"


def test_label_column_override_top_level() -> None:
    assert _label_column({"label_column": "louvain"}) == "louvain"


def test_label_column_override_in_expected() -> None:
    assert _label_column({"expected": {"label_column": "cluster"}}) == "cluster"


# --------------------------- P1-8: orchestrator _run ---------------------- #


def test_run_raises_on_nonzero_exit() -> None:
    """_run must raise on subprocess failure (previously silently continued)."""
    with patch("skillprism.orchestrator.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        with pytest.raises(RuntimeError, match="Command failed"):
            _run(["evaluate-skill", "--all"])


def test_run_returns_zero_on_success() -> None:
    with patch("skillprism.orchestrator.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert _run(["echo", "hi"]) == 0
