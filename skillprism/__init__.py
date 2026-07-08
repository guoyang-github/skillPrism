"""Skill Validation: a project-agnostic framework for evaluating and optimizing AI agent skills."""

__version__ = "2.1.0"

from .evaluate_skill_rubric import (
    evaluate_skill,
    format_report_markdown,
    format_scorecard,
    load_config,
)
from .evaluate_skill_rubric import (
    main as evaluate_main,
)
from .optimize_skill import main as optimize_main

__all__ = [
    "__version__",
    "evaluate_main",
    "optimize_main",
    "evaluate_skill",
    "format_report_markdown",
    "format_scorecard",
    "load_config",
]
