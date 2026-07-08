#!/usr/bin/env python3
"""P2-4: config schema validation surfaces YAML typos instead of silent fallback."""

from __future__ import annotations

import pytest

from skillprism.config_schema import validate_config


def test_valid_config_passes() -> None:
    config = {
        "schema_version": "1.0",
        "scoring": {"weights": {"D1": 0.1}, "grade_thresholds": {"A": 90}},
        "skill_types": {"analysis": {}},
    }
    # Should not raise.
    assert validate_config(config) is config


def test_unknown_top_level_key_warns(tmp_path, capsys) -> None:
    config = {"scoring": {"weights": {}}, "wieghts": {"D1": 0.1}}
    validate_config(config)
    captured = capsys.readouterr()
    assert "wieghts" in captured.err


def test_unknown_scoring_key_warns(capsys) -> None:
    config = {"scoring": {"wieghts": {"D1": 0.1}}}
    validate_config(config)
    captured = capsys.readouterr()
    assert "scoring.wieghts" in captured.err


def test_scoring_wrong_type_raises() -> None:
    with pytest.raises(ValueError, match="scoring"):
        validate_config({"scoring": "not a mapping"})


def test_weights_wrong_type_raises() -> None:
    with pytest.raises(ValueError, match="scoring.weights"):
        validate_config({"scoring": {"weights": [0.1, 0.2]}})


def test_non_mapping_config_raises() -> None:
    with pytest.raises(ValueError, match="mapping"):
        validate_config("not a dict")  # type: ignore[arg-type]


def test_skill_types_wrong_type_raises() -> None:
    with pytest.raises(ValueError, match="skill_types"):
        validate_config({"skill_types": "analysis"})
