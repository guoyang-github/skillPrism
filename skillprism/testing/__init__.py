#!/usr/bin/env python3
"""skillPrism testing utilities.

Public helpers for generating mock data, running boundary tests, and writing
pytest-based Skill tests.
"""

from __future__ import annotations

from .boundary import (
    BoundaryCase,
    BoundaryReport,
    BoundaryTestResult,
    format_boundary_report,
    run_boundary_cases,
    run_task_boundary_tests,
)
from .mock_data import (
    generate_anndata,
    generate_document_prompt,
    generate_table_csv,
    generate_visium_data,
)

__all__ = [
    "BoundaryCase",
    "BoundaryReport",
    "BoundaryTestResult",
    "format_boundary_report",
    "generate_anndata",
    "generate_document_prompt",
    "generate_table_csv",
    "generate_visium_data",
    "run_boundary_cases",
    "run_task_boundary_tests",
]
