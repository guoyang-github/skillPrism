#!/usr/bin/env python3
"""Benchmark-facing mock data helpers.

This thin shim re-exports `skillprism.testing.mock_data` so that benchmark
runners and registry configs can generate synthetic data without importing from
the internal testing package directly.
"""

from __future__ import annotations

from skillprism.testing.mock_data import (
    generate_anndata,
    generate_document_prompt,
    generate_table_csv,
    generate_visium_data,
)

__all__ = [
    "generate_anndata",
    "generate_document_prompt",
    "generate_table_csv",
    "generate_visium_data",
]
