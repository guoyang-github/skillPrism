#!/usr/bin/env python3
"""Integration test for the cell2location benchmark example.

Requires the example data to be generated first:
    python examples/benchmark_cell2location/scripts/generate_data.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skillprism.benchmark.runner import run_benchmarks
from skillprism.gradual import run_gradual_pipeline

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "benchmark_cell2location"
REGISTRY_PATH = (
    EXAMPLE_DIR / "benchmarks" / "bio-spatial-deconvolution-cell2location" / "registry.yaml"
)
CODE_PATH = EXAMPLE_DIR / "scripts" / "run_c2l.py"


@pytest.mark.skipif(not REGISTRY_PATH.exists(), reason="cell2location example not present")
def test_cell2location_level0_passes() -> None:
    results = run_benchmarks(
        "bio-spatial-deconvolution-cell2location",
        REGISTRY_PATH,
        code_path=CODE_PATH,
        level=0,
        results_mode=False,
    )
    assert results["_all_pass"] is True
    assert "c2l_level0_smoke" in results["benchmarks"]


@pytest.mark.skipif(not REGISTRY_PATH.exists(), reason="cell2location example not present")
def test_cell2location_darwin_up_to_level2() -> None:
    overall = run_gradual_pipeline(
        "bio-spatial-deconvolution-cell2location",
        REGISTRY_PATH,
        max_level=2,
        base_output_dir=EXAMPLE_DIR / "artifacts",
        ratchet=False,
        code_path=CODE_PATH,
        results_mode=False,
    )
    assert overall["_all_pass"] is True
    assert set(overall["stages"].keys()) == {"level0", "level1", "level2"}
