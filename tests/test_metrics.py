#!/usr/bin/env python3
"""Unit tests for skillPrism benchmark metrics."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillprism.benchmark.evaluators import GenericEvaluator
from skillprism.benchmark.metrics import (
    _extract_headers,
    _tokenize,
    mean_rmse,
    metric_passes,
)


class TestMetricPasses:
    def test_min_pass(self) -> None:
        assert metric_passes(0.8, {"type": "min", "threshold": 0.7})

    def test_min_fail(self) -> None:
        assert not metric_passes(0.6, {"type": "min", "threshold": 0.7})

    def test_max_pass(self) -> None:
        assert metric_passes(0.4, {"type": "max", "threshold": 0.5})

    def test_max_fail(self) -> None:
        assert not metric_passes(0.6, {"type": "max", "threshold": 0.5})

    def test_range_pass(self) -> None:
        assert metric_passes(5, {"type": "range", "min": 3, "max": 8})

    def test_range_fail(self) -> None:
        assert not metric_passes(10, {"type": "range", "min": 3, "max": 8})

    def test_tolerance_pass(self) -> None:
        assert metric_passes(1.02, {"type": "tolerance", "reference": 1.0, "threshold": 0.03})

    def test_tolerance_fail(self) -> None:
        assert not metric_passes(1.1, {"type": "tolerance", "reference": 1.0, "threshold": 0.03})

    def test_exact_pass(self) -> None:
        assert metric_passes(42, {"type": "exact", "expected": 42})

    def test_exact_fail(self) -> None:
        assert not metric_passes(43, {"type": "exact", "expected": 42})

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown metric type"):
            metric_passes(1.0, {"type": "unknown"})


class TestDocumentHelpers:
    def test_extract_headers(self) -> None:
        text = "# Title\n## Section A\n### Sub\nplain line\n## Section A"
        assert _extract_headers(text) == {"title", "section a", "sub"}

    def test_extract_no_headers(self) -> None:
        assert _extract_headers("no headers here") == set()

    def test_tokenize(self) -> None:
        assert _tokenize("Hello, world! HELLO.") == {"hello", "world"}


class TestEvaluateDocument:
    def test_identical_documents_pass(self, tmp_path: Path) -> None:
        doc = tmp_path / "doc.md"
        doc.write_text("# Title\n\nHello world.\n")
        metrics_spec = [
            {"id": "section_overlap", "type": "min", "threshold": 0.6},
            {"id": "token_jaccard", "type": "min", "threshold": 0.3},
            {"id": "length_ratio", "type": "range", "min": 0.5, "max": 2.0},
        ]
        result = GenericEvaluator().evaluate(doc, doc, metrics_spec, {})
        assert result["section_overlap"] == 1.0
        assert result["token_jaccard"] == 1.0
        assert result["length_ratio"] == 1.0
        assert result["_all_pass"] is True

    def test_partial_match(self, tmp_path: Path) -> None:
        output = tmp_path / "output.md"
        expected = tmp_path / "expected.md"
        expected.write_text("# Title\n\nHello world and more words.\n")
        output.write_text("# Title\n\nHello world.\n")
        result = GenericEvaluator().evaluate(
            output,
            expected,
            [
                {"id": "section_overlap", "type": "min", "threshold": 0.0},
                {"id": "token_jaccard", "type": "min", "threshold": 0.0},
                {"id": "length_ratio", "type": "range", "min": 0.0, "max": 10.0},
            ],
            {},
        )
        assert result["section_overlap"] == 1.0
        assert 0.0 < result["token_jaccard"] < 1.0
        assert 0.0 < result["length_ratio"] < 1.0

    def test_missing_expected_is_handled(self, tmp_path: Path) -> None:
        output = tmp_path / "output.md"
        output.write_text("# Title\n\nHello world.\n")
        result = GenericEvaluator().evaluate(
            output,
            None,
            [
                {"id": "section_overlap", "type": "min", "threshold": 0.0},
                {"id": "token_jaccard", "type": "min", "threshold": 0.0},
                {"id": "length_ratio", "type": "range", "min": 0.0, "max": 10.0},
            ],
            {},
        )
        assert result["section_overlap"] == 0.0
        assert result["token_jaccard"] == 0.0
        assert result["length_ratio"] == 1.0


class TestEvaluateTable:
    def test_basic_csv(self, tmp_path: Path) -> None:
        out = tmp_path / "out.csv"
        out.write_text("name,value\nfoo,1\nbar,2\n")
        result = GenericEvaluator().evaluate(
            out,
            None,
            [
                {"id": "row_count", "type": "min", "threshold": 1},
                {"id": "col_count", "type": "min", "threshold": 1},
            ],
            {},
        )
        assert result["row_count"] == 2
        assert result["col_count"] == 2

    def test_expected_diff_rows(self, tmp_path: Path) -> None:
        out = tmp_path / "out.csv"
        exp = tmp_path / "exp.csv"
        out.write_text("a,b\n1,2\n")
        exp.write_text("a,b\n1,2\n3,4\n")
        result = GenericEvaluator().evaluate(
            out,
            exp,
            [{"id": "expected_diff_rows", "type": "exact", "expected": 1}],
            {},
        )
        assert result["expected_diff_rows"] == 1


class TestEvaluateDeconvolution:
    def _write_props(
        self, path: Path, values: list[list[float]], index: list[str], columns: list[str]
    ) -> None:
        import pandas as pd

        df = pd.DataFrame(values, index=index, columns=columns)
        df.index.name = "spot_id"
        df.to_csv(path)

    def test_identical_proportions_pass(self, tmp_path: Path) -> None:
        out = tmp_path / "proportions.csv"
        exp = tmp_path / "expected.csv"
        values = [[0.5, 0.3, 0.2], [0.2, 0.5, 0.3]]
        self._write_props(out, values, ["spot_0", "spot_1"], ["A", "B", "C"])
        self._write_props(exp, values, ["spot_0", "spot_1"], ["A", "B", "C"])

        metrics_spec = [
            {"id": "mean_rmse", "type": "max", "threshold": 0.01},
            {"id": "mean_pearson", "type": "min", "threshold": 0.99},
        ]
        result = GenericEvaluator().evaluate(out, exp, metrics_spec, {})
        assert result["mean_rmse"] < 0.01
        assert result["mean_pearson"] >= 0.99
        assert result["_all_pass"] is True

    def test_partial_proportions(self, tmp_path: Path) -> None:
        out = tmp_path / "proportions.csv"
        exp = tmp_path / "expected.csv"
        self._write_props(
            out,
            [[0.5, 0.3, 0.2], [0.2, 0.5, 0.3], [0.3, 0.2, 0.5]],
            ["spot_0", "spot_1", "spot_2"],
            ["A", "B", "C"],
        )
        self._write_props(
            exp,
            [[0.4, 0.4, 0.2], [0.3, 0.4, 0.3], [0.2, 0.3, 0.5]],
            ["spot_0", "spot_1", "spot_2"],
            ["A", "B", "C"],
        )

        result = GenericEvaluator().evaluate(
            out,
            exp,
            [
                {"id": "mean_rmse", "type": "max", "threshold": 1.0},
                {"id": "mean_pearson", "type": "min", "threshold": 0.0},
                {"id": "mean_jsd", "type": "max", "threshold": 1.0},
            ],
            {},
        )
        assert result["mean_rmse"] > 0
        assert 0.0 < result["mean_pearson"] < 1.0
        assert "mean_jsd" in result

    def test_missing_expected(self, tmp_path: Path) -> None:
        out = tmp_path / "proportions.csv"
        self._write_props(out, [[0.5, 0.3, 0.2]], ["spot_0"], ["A", "B", "C"])
        result = GenericEvaluator().evaluate(
            out,
            None,
            [
                {"id": "n_spots", "type": "min", "threshold": 1},
                {"id": "n_cell_types", "type": "min", "threshold": 1},
                {"id": "mean_rmse", "type": "max", "threshold": 1.0},
            ],
            {},
        )
        assert result["n_spots"] == 1
        assert result["n_cell_types"] == 3
        assert result["mean_rmse"] is None

    def test_mismatched_index_columns(self, tmp_path: Path) -> None:
        out = tmp_path / "proportions.csv"
        exp = tmp_path / "expected.csv"
        self._write_props(out, [[0.5, 0.5]], ["spot_0"], ["A", "B"])
        self._write_props(exp, [[0.5, 0.5]], ["spot_1"], ["C", "D"])
        result = GenericEvaluator().evaluate(
            out, exp, [{"id": "mean_rmse", "type": "max", "threshold": 1.0}], {}
        )
        assert result["mean_rmse"] is None


class TestDeconvolutionEvaluatorNormalization:
    """Production path (metrics.mean_rmse) must row-normalize like before."""

    def _write_props(
        self, path: Path, values: list[list[float]], index: list[str], columns: list[str]
    ) -> None:
        import pandas as pd

        df = pd.DataFrame(values, index=index, columns=columns)
        df.index.name = "spot_id"
        df.to_csv(path)

    def test_scaled_proportions_compare_as_equal(self, tmp_path: Path) -> None:
        """Output summing to 100 vs expected summing to 1 (same proportions) → RMSE≈0."""
        out = tmp_path / "proportions.csv"
        exp = tmp_path / "expected.csv"
        # Same proportions, different scales (100x vs 1x).
        self._write_props(
            out, [[50.0, 30.0, 20.0], [20.0, 50.0, 30.0]], ["s0", "s1"], ["A", "B", "C"]
        )
        self._write_props(exp, [[0.5, 0.3, 0.2], [0.2, 0.5, 0.3]], ["s0", "s1"], ["A", "B", "C"])

        rmse = mean_rmse(out, exp, {})
        assert rmse is not None
        assert rmse < 0.01, f"scaled-equivalent proportions must have ~0 RMSE, got {rmse}"

    def test_zero_sum_row_left_unchanged(self, tmp_path: Path) -> None:
        """A zero-sum row must not produce NaN via divide-by-zero."""
        out = tmp_path / "proportions.csv"
        exp = tmp_path / "expected.csv"
        self._write_props(out, [[0.5, 0.5], [0.0, 0.0]], ["s0", "s1"], ["A", "B"])
        self._write_props(exp, [[0.5, 0.5], [0.0, 0.0]], ["s0", "s1"], ["A", "B"])
        rmse = mean_rmse(out, exp, {})
        assert rmse is not None
        assert rmse == rmse  # not NaN
