#!/usr/bin/env python3
"""Lightweight config schema validation for ``skill_rubric_types.yaml``.

A typo in the YAML (e.g. ``wieghts:`` instead of ``weights:``, or
``scoring:`` set to a string) previously fell back to defaults silently, so
the engine reported scores that did not match the user's intent. This module
validates the loaded config's shape and surfaces problems loudly (stderr
warnings for soft issues, ``ValueError`` for hard type errors) instead of
failing quietly.
"""

from __future__ import annotations

import sys
from typing import Any, Dict

# Recognized top-level keys (extras are likely typos → warned).
KNOWN_TOP_LEVEL = {
    "schema_version",
    "scoring",
    "llm_tasks",
    "security",
    "required_frontmatter_base",
    "dimension_names",
    "skill_types",
    "llm_judge",
    "editor",
    "optimization",
}

# Expected shape of frequently-typo'd nested sections.
_SCORING_KEYS = {"weights", "grade_thresholds"}

# Valid dimension codes in this rubric.
_VALID_DIMENSIONS = {f"D{i}" for i in range(1, 10)}

# Tolerance for floating-point weight sums.
_WEIGHT_SUM_TOLERANCE = 0.02


def _warn(msg: str) -> None:
    print(f"Warning [config]: {msg}", file=sys.stderr)


def _validate_dimensions(keys: Any, path: str) -> None:
    """Warn if any key in *keys* is not a recognized dimension code."""
    if not isinstance(keys, (list, tuple, dict)):
        return
    iterable = keys if isinstance(keys, (list, tuple)) else keys.keys()
    for dim in iterable:
        if isinstance(dim, str) and dim not in _VALID_DIMENSIONS:
            _warn(
                f"{path} references unknown dimension '{dim}' (known: {sorted(_VALID_DIMENSIONS)})"
            )


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the shape of a loaded skill-rubric config.

    Prints warnings for suspicious/unknown keys; raises ``ValueError`` for
    hard type errors (a section that should be a mapping but is not). The
    engine keeps working with defaults for genuinely-missing optional sections.
    """
    if not isinstance(config, dict):
        raise ValueError(f"config must be a mapping, got {type(config).__name__}")

    # Unknown top-level keys → likely typos.
    for key in config:
        if key not in KNOWN_TOP_LEVEL:
            _warn(f"unknown top-level key '{key}' (known: {sorted(KNOWN_TOP_LEVEL)})")

    # scoring section
    scoring = config.get("scoring")
    if scoring is not None:
        if not isinstance(scoring, dict):
            raise ValueError(f"'scoring' must be a mapping, got {type(scoring).__name__}")
        for key in scoring:
            if key not in _SCORING_KEYS:
                _warn(f"unknown key 'scoring.{key}' (known: {sorted(_SCORING_KEYS)})")
        weights = scoring.get("weights")
        if weights is not None:
            if not isinstance(weights, dict):
                raise ValueError(
                    f"'scoring.weights' must be a mapping, got {type(weights).__name__}"
                )
            _validate_dimensions(weights.keys(), "scoring.weights")
            total = sum(float(w) for w in weights.values() if isinstance(w, (int, float)))
            if total > 0 and abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
                _warn(f"scoring.weights sum to {total:.4f}, expected ~1.0")
        thresholds = scoring.get("grade_thresholds")
        if thresholds is not None and not isinstance(thresholds, dict):
            raise ValueError(
                f"'scoring.grade_thresholds' must be a mapping, got {type(thresholds).__name__}"
            )

    # skill_types / llm_judge / editor / optimization should be mappings if present.
    for section in ("skill_types", "llm_judge", "editor", "optimization", "security"):
        val = config.get(section)
        if val is not None and not isinstance(val, dict):
            raise ValueError(f"'{section}' must be a mapping, got {type(val).__name__}")

    # Validate dimension references inside skill types.
    skill_types = config.get("skill_types") or {}
    for skill_type, cfg in skill_types.items():
        if not isinstance(cfg, dict):
            raise ValueError(
                f"'skill_types.{skill_type}' must be a mapping, got {type(cfg).__name__}"
            )
        _validate_dimensions(
            cfg.get("dimension_names_override", {}).keys(),
            f"skill_types.{skill_type}.dimension_names_override",
        )
        _validate_dimensions(
            cfg.get("dimension_checks", {}).keys(),
            f"skill_types.{skill_type}.dimension_checks",
        )
        enabled_dimensions = cfg.get("enabled_dimensions")
        if enabled_dimensions is not None:
            if not isinstance(enabled_dimensions, list):
                raise ValueError(
                    f"'skill_types.{skill_type}.enabled_dimensions' must be a list, "
                    f"got {type(enabled_dimensions).__name__}"
                )
            _validate_dimensions(
                enabled_dimensions,
                f"skill_types.{skill_type}.enabled_dimensions",
            )

    # Validate optimization cluster dimension references and threshold ordering.
    optimization = config.get("optimization") or {}
    priority = optimization.get("priority") or {}
    _validate_dimensions(priority.get("blockers", []), "optimization.priority.blockers")
    _validate_dimensions(priority.get("high_roi", []), "optimization.priority.high_roi")
    blocker_threshold = priority.get("blocker_threshold")
    improvement_threshold = priority.get("improvement_threshold")
    if (
        isinstance(blocker_threshold, (int, float))
        and isinstance(improvement_threshold, (int, float))
        and blocker_threshold > improvement_threshold
    ):
        _warn(
            f"optimization.priority.blocker_threshold ({blocker_threshold}) is greater than "
            f"improvement_threshold ({improvement_threshold}); blockers should be <= improvements"
        )
    for idx, cluster in enumerate(optimization.get("clusters", [])):
        _validate_dimensions(
            cluster.get("dimensions", []),
            f"optimization.clusters[{idx}].dimensions",
        )

    # Validate dimension_names keys.
    dimension_names = config.get("dimension_names")
    if dimension_names is not None:
        if not isinstance(dimension_names, dict):
            raise ValueError(
                f"'dimension_names' must be a mapping, got {type(dimension_names).__name__}"
            )
        _validate_dimensions(dimension_names, "dimension_names")

    return config
