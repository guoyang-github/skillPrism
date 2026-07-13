#!/usr/bin/env python3
"""Experiment history tracking for skill optimization.

Uses JSONL for easy parsing and integration with Python tooling. Each
evaluate-skill and improve-skill run appends a record to
``artifacts/<skill>/history.jsonl`` (relative to the
current working directory), keeping the skill source tree read-only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .test_prompts import artifacts_dir


@dataclass
class OptimizationRecord:
    timestamp: str
    skill: str
    commit_or_backup: str
    old_score: float
    new_score: float
    status: str  # baseline / keep / revert / error / human-decide
    dimension: str
    note: str
    eval_mode: str  # full_test / dry_run / static
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


HISTORY_FILENAME = "history.jsonl"


def history_path(skill_path: Path) -> Path:
    return artifacts_dir(skill_path) / HISTORY_FILENAME


def load_history(skill_path: Path) -> List[OptimizationRecord]:
    path = history_path(skill_path)
    if not path.exists():
        return []
    records: List[OptimizationRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            records.append(OptimizationRecord(**data))
        except Exception as exc:
            # A single malformed line previously caused a silent truncated load.
            # Surface it so history corruption is visible (the line is skipped,
            # not fatal).
            print(f"Warning: skipping malformed history line: {exc}")
            continue
    return records


def append_record(skill_path: Path, record: OptimizationRecord) -> Path:
    path = history_path(skill_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    return path


def record_baseline(
    skill_path: Path,
    score: float,
    note: str = "baseline evaluation",
    eval_mode: str = "static",
    commit_or_backup: str = "",
) -> OptimizationRecord:
    record = OptimizationRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        skill=str(skill_path),
        commit_or_backup=commit_or_backup,
        old_score=score,
        new_score=score,
        status="baseline",
        dimension="all",
        note=note,
        eval_mode=eval_mode,
    )
    append_record(skill_path, record)
    return record


def record_attempt(
    skill_path: Path,
    old_score: float,
    new_score: float,
    status: str,
    dimension: str,
    note: str = "",
    eval_mode: str = "static",
    commit_or_backup: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> OptimizationRecord:
    record = OptimizationRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        skill=str(skill_path),
        commit_or_backup=commit_or_backup,
        old_score=old_score,
        new_score=new_score,
        status=status,
        dimension=dimension,
        note=note,
        eval_mode=eval_mode,
        metadata=metadata or {},
    )
    append_record(skill_path, record)
    return record


def format_history_table(records: List[OptimizationRecord]) -> str:
    if not records:
        return "No optimization history found."

    lines = [
        "| Timestamp | Status | Dim | Old | New | Δ | Note | Mode |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        delta = f"{r.new_score - r.old_score:+.1f}"
        ts = r.timestamp[:19].replace("T", " ")
        lines.append(
            f"| {ts} | {r.status} | {r.dimension} | {r.old_score} | "
            f"{r.new_score} | {delta} | {r.note} | {r.eval_mode} |"
        )
    return "\n".join(lines)


def get_best_score(records: List[OptimizationRecord]) -> Optional[float]:
    keep_records = [r for r in records if r.status in ("keep", "baseline")]
    if not keep_records:
        return None
    return max(r.new_score for r in keep_records)


def get_summary(records: List[OptimizationRecord]) -> Dict[str, Any]:
    if not records:
        return {"total": 0, "kept": 0, "reverted": 0, "best_score": None}
    return {
        "total": len(records),
        "kept": sum(1 for r in records if r.status == "keep"),
        "reverted": sum(1 for r in records if r.status == "revert"),
        "errors": sum(1 for r in records if r.status == "error"),
        "best_score": get_best_score(records),
    }
