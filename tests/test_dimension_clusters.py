from dataclasses import dataclass

from skillprism.dimension_clusters import (
    analyze_clusters,
    find_cluster,
    format_cluster_analysis,
    get_related_dimensions,
)


@dataclass
class FakeDim:
    code: str
    score: int


def test_find_cluster():
    assert find_cluster("D2").name == "Structure cluster"
    assert find_cluster("D9").name == "Maintenance cluster"


def test_get_related_dimensions():
    related = get_related_dimensions("D2")
    assert "D1" in related
    assert "D2" not in related


def test_analyze_clusters():
    dims = [FakeDim("D2", 1), FakeDim("D3", 4), FakeDim("D4", 4)]
    analysis = analyze_clusters(dims)
    assert analysis["weakest"] == "D2"
    assert analysis["cluster"] == "Structure cluster"
    assert len(analysis["related"]) > 0


def test_format_cluster_analysis():
    dims = [FakeDim("D2", 1), FakeDim("D3", 4)]
    text = format_cluster_analysis(dims)
    assert "Weakest dimension" in text
    assert "Structure cluster" in text
