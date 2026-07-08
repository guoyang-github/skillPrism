#!/usr/bin/env python3
"""Tests for editor strategy selection and dimension clustering."""

from __future__ import annotations

from skillprism.editor_strategies import (
    DIMENSION_CLUSTERS,
    find_related_dimensions,
    get_dimension_clusters,
    get_strategy,
)


def test_get_strategy_single_dimension() -> None:
    strategy = get_strategy("D4")
    assert "requirements.txt" in strategy


def test_get_strategy_with_related_dimensions() -> None:
    strategy = get_strategy("D2", related=["D6"])
    assert "Primary focus (D2)" in strategy
    assert "D6" in strategy


def test_get_strategy_fallback() -> None:
    strategy = get_strategy("DX")
    assert "Improve dimension DX" in strategy


def test_default_clusters() -> None:
    assert "documentation_callability" in DIMENSION_CLUSTERS
    assert set(DIMENSION_CLUSTERS["documentation_callability"]) == {"D2", "D6"}


def test_find_related_dimensions() -> None:
    dimension_scores = {"D2": 2, "D6": 2, "D4": 4}
    related = find_related_dimensions("D2", dimension_scores, config=None, threshold=3)
    assert "D6" in related
    assert "D4" not in related


def test_get_dimension_clusters_from_config() -> None:
    config = {
        "optimization": {
            "clusters": [
                {"name": "test_cluster", "dimensions": ["D1", "D2"]},
            ]
        }
    }
    clusters = get_dimension_clusters(config)
    assert "test_cluster" in clusters
    assert clusters["test_cluster"] == ["D1", "D2"]
