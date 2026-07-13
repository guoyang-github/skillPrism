#!/usr/bin/env python3
"""Baseline persistence and code-asset snapshot helpers for skillPrism."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, cast

from ._locking import atomic_write_text, prune_rolling_backups
from .evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    SkillReport,
    get_weights,
    load_config,
)
from .test_prompts import baseline_dir

BASELINE_FILE = "baseline.json"

CODE_ASSET_PATTERNS = [
    "scripts",
    "examples",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Makefile",
]


def _baseline_path(skill_path: Path) -> Path:
    return baseline_dir(skill_path) / BASELINE_FILE


def _baseline_bak_path(skill_path: Path) -> Path:
    return baseline_dir(skill_path) / f"{BASELINE_FILE}.bak"


def load_baseline(skill_path: Path) -> Optional[Dict[str, Any]]:
    """Load the baseline JSON, falling back to the ``.bak`` copy on corruption.

    Previously a truncated (mid-crash) baseline file raised ``JSONDecodeError``
    and broke every subsequent run. Now a parse failure on the primary file
    transparently falls back to the ``.bak`` written alongside it.
    """
    path = _baseline_path(skill_path)
    if not path.exists():
        return None
    for candidate in (path, _baseline_bak_path(skill_path)):
        if not candidate.exists():
            continue
        try:
            return cast(Dict[str, Any], json.loads(candidate.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return None


def save_baseline(
    skill_path: Path,
    report: SkillReport,
    benchmark: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist the current rubric score and a copy of SKILL.md for rollback."""
    weights = get_weights(load_config(DEFAULT_CONFIG))
    score = report.fused_score(weights, 0.0)
    existing = load_baseline(skill_path) or {}
    historical_best = max(existing.get("historical_best_score", score), score)
    data: Dict[str, Any] = {
        "score": score,
        "grade": report.grade(
            score,
            load_config(DEFAULT_CONFIG).get("scoring", {}).get("grade_thresholds", {}),
        ),
        "dimension_scores": {d.code: d.score for d in report.dimensions},
        "benchmark": benchmark or {},
        "historical_best_score": historical_best,
    }
    payload = json.dumps(data, indent=2)

    # Atomic write of the primary JSON + a .bak for corruption recovery.
    target_dir = baseline_dir(skill_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(_baseline_path(skill_path), payload)
    atomic_write_text(_baseline_bak_path(skill_path), payload)

    # Also save a copy of SKILL.md for bloat detection and rollback
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        atomic_write_text(target_dir / "SKILL.md", content)
        # Stable backup used by bloat detection and manual recovery.
        atomic_write_text(target_dir / "SKILL.md.bak", content)
        # Timestamped backup for recovery from corruption
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        atomic_write_text(target_dir / f"SKILL.md.bak.{ts}", content)
        # Prune rolling backups to the most recent few.
        prune_rolling_backups(target_dir, "SKILL.md.bak.*", keep=5)
    return data


def load_baseline_skill_md(skill_path: Path) -> str:
    baseline_md = baseline_dir(skill_path) / "SKILL.md"
    if baseline_md.exists():
        return baseline_md.read_text(encoding="utf-8", errors="replace")
    return ""


def clear_baseline(skill_path: Path) -> None:
    """Remove the persisted baseline JSON for a skill."""
    path = _baseline_path(skill_path)
    if path.exists():
        path.unlink()


def snapshot_code_assets(skill_path: Path) -> Path:
    """Copy editable code assets into the baseline snapshot directory."""
    snapshot_dir = baseline_dir(skill_path) / "code_snapshot"
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for pattern in CODE_ASSET_PATTERNS:
        src = skill_path / pattern
        if not src.exists():
            continue
        dst = snapshot_dir / pattern
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    return snapshot_dir


def restore_code_assets(skill_path: Path) -> bool:
    """Restore code assets from the baseline snapshot directory.

    Returns True if a snapshot existed and was restored, False otherwise.
    """
    snapshot_dir = baseline_dir(skill_path) / "code_snapshot"
    if not snapshot_dir.exists():
        return False

    for pattern in CODE_ASSET_PATTERNS:
        src = snapshot_dir / pattern
        dst = skill_path / pattern
        if not src.exists():
            continue
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    return True
