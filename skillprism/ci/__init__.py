#!/usr/bin/env python3
"""CI integration for skillPrism benchmarks.

Provides a reusable pipeline that runs benchmark suites, compares them against
a baseline, and optionally ratchets the baseline forward when all checks pass.
"""

from .pipeline import CIPipeline, run_ci_pipeline
from .reports import format_report, write_report

__all__ = ["CIPipeline", "run_ci_pipeline", "format_report", "write_report"]
