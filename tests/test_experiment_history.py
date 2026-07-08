from pathlib import Path

from skillprism.experiment_history import (
    format_history_table,
    get_best_score,
    get_summary,
    history_path,
    load_history,
    record_attempt,
    record_baseline,
)


def test_history_path(tmp_path: Path):
    assert history_path(tmp_path) == tmp_path / ".skillprism_history.jsonl"


def test_record_baseline(tmp_path: Path):
    record = record_baseline(tmp_path, 72.5, note="initial baseline")
    assert record.status == "baseline"
    assert record.new_score == 72.5
    assert history_path(tmp_path).exists()


def test_record_attempt(tmp_path: Path):
    record_attempt(tmp_path, 72.5, 78.0, "keep", "D3", note="added fallback")
    records = load_history(tmp_path)
    assert len(records) == 1
    assert records[0].status == "keep"
    assert records[0].dimension == "D3"


def test_load_history_ignores_bad_lines(tmp_path: Path):
    history_path(tmp_path).write_text("not json\n", encoding="utf-8")
    records = load_history(tmp_path)
    assert records == []


def test_get_best_score(tmp_path: Path):
    record_baseline(tmp_path, 70.0)
    record_attempt(tmp_path, 70.0, 75.0, "keep", "D3")
    record_attempt(tmp_path, 75.0, 73.0, "revert", "D5")
    records = load_history(tmp_path)
    assert get_best_score(records) == 75.0


def test_format_history_table(tmp_path: Path):
    record_baseline(tmp_path, 70.0)
    table = format_history_table(load_history(tmp_path))
    assert "baseline" in table


def test_get_summary(tmp_path: Path):
    record_baseline(tmp_path, 70.0)
    record_attempt(tmp_path, 70.0, 75.0, "keep", "D3")
    record_attempt(tmp_path, 75.0, 73.0, "revert", "D5")
    summary = get_summary(load_history(tmp_path))
    assert summary["total"] == 3
    assert summary["kept"] == 1
    assert summary["reverted"] == 1
