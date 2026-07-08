#!/usr/bin/env python3
"""Dimension cluster analysis for skill optimization.

Inspired by darwin-skill's observation that some rubric dimensions are
correlated (e.g. improving D3 often lifts D2 and D4). This module helps the
optimizer avoid redundant edits by showing which dimensions move together.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DimensionCluster:
    name: str
    dimensions: List[str]
    note: str


CLUSTERS: List[DimensionCluster] = [
    DimensionCluster(
        name="Structure cluster",
        dimensions=["D1", "D2", "D3", "D4"],
        note="Improving one structural dimension often lifts the others. "
        "When the weakest dimension is in this cluster, check whether "
        "related dimensions are already near their ceiling.",
    ),
    DimensionCluster(
        name="Execution cluster",
        dimensions=["D3", "D5", "D6"],
        note="Executability, specificity, and LLM-callability are tightly coupled. "
        "Adding concrete parameters and examples usually helps all three.",
    ),
    DimensionCluster(
        name="Maintenance cluster",
        dimensions=["D7", "D8", "D9"],
        note="Robustness, maintainability, and security reflect long-term quality. "
        "Fixing failure modes and blacklists tends to lift this group.",
    ),
]


def find_cluster(dimension_code: str) -> Optional[DimensionCluster]:
    for cluster in CLUSTERS:
        if dimension_code in cluster.dimensions:
            return cluster
    return None


def get_related_dimensions(dimension_code: str) -> List[str]:
    cluster = find_cluster(dimension_code)
    if not cluster:
        return []
    return [d for d in cluster.dimensions if d != dimension_code]


def analyze_clusters(dimensions: List[Any]) -> Dict[str, Any]:
    """Return cluster analysis for the given dimension scores."""

    def _code_score(dim: Any) -> Optional[Tuple[str, int]]:
        if isinstance(dim, dict):
            code = dim.get("code")
            score = dim.get("score", 0)
        else:
            code = getattr(dim, "code", None)
            score = getattr(dim, "score", 0)
        if isinstance(code, str) and isinstance(score, int):
            return code, score
        return None

    scores: Dict[str, int] = {}
    for dim in dimensions:
        pair = _code_score(dim)
        if pair:
            scores[pair[0]] = pair[1]

    if not scores:
        return {}

    weakest = min(scores.items(), key=lambda x: x[1])[0]
    cluster = find_cluster(weakest)
    related = []
    if cluster:
        related = [{"code": d, "score": scores.get(d)} for d in cluster.dimensions if d != weakest]

    return {
        "weakest": weakest,
        "weakest_score": scores.get(weakest),
        "cluster": cluster.name if cluster else None,
        "related": related,
        "note": cluster.note if cluster else None,
    }


def format_cluster_analysis(dimensions: List[Any]) -> str:
    analysis = analyze_clusters(dimensions)
    if not analysis:
        return "No dimensions available for cluster analysis."

    lines = ["### Dimension Cluster Analysis", ""]
    lines.append(f"Weakest dimension: **{analysis['weakest']}** ({analysis['weakest_score']}/5)")
    if analysis["cluster"]:
        lines.append(f"Cluster: {analysis['cluster']}")
        lines.append(f"> {analysis['note']}")
        if analysis["related"]:
            lines.append("")
            lines.append("Related dimensions in the same cluster:")
            for r in analysis["related"]:
                lines.append(f"- {r['code']}: {r['score']}/5")
    return "\n".join(lines)
