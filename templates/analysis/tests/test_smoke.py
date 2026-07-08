"""Smoke tests for skill-name-kebab-case."""

import subprocess
import sys
from pathlib import Path

import pytest

scanpy = pytest.importorskip("scanpy")


def test_minimal_example_runs():
    """The built-in minimal example should run end-to-end."""
    example = Path(__file__).resolve().parent.parent / "examples" / "minimal_example.py"
    assert example.exists(), f"minimal example not found: {example}"
    result = subprocess.run(
        [sys.executable, str(example)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "Clusters:" in result.stdout
