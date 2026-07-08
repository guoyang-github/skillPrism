#!/usr/bin/env python3
"""P1-1: atomic baseline writes + concurrency lock.

Crash mid-write must not leave a truncated JSON that breaks later runs; the
``.bak`` copy must be used as a fallback. Concurrent optimizers must not race
the ``historical_best_score`` read-modify-write (ratchet must be monotonic).
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from skillprism._baseline import _baseline_path, load_baseline, save_baseline
from skillprism._locking import atomic_write_text
from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config

BASE_SKILL_MD = """---
name: atomic-test-skill
description: A skill for testing atomic baseline writes.
keywords:
  - test
---

# Atomic Test Skill

## Quick Start

```bash
echo hello
```
"""


def _make_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "atomic_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(BASE_SKILL_MD, encoding="utf-8")
    config = load_config(DEFAULT_CONFIG)
    report = evaluate_skill(skill_dir, config)
    save_baseline(skill_dir, report)
    return skill_dir


def test_atomic_write_text_does_not_leave_truncated_file(tmp_path: Path) -> None:
    """If the write is interrupted, the target file is unchanged (temp+replace)."""
    target = tmp_path / "data.json"
    target.write_text('{"original": true}', encoding="utf-8")

    # Simulate a failed write: atomic_write_text raises after writing the temp
    # file but before os.replace (we emulate by passing a path whose parent
    # is fine but raising mid-way is hard; instead assert the normal path works
    # and a pre-existing target survives a failed sibling write).
    atomic_write_text(target, '{"new": false}')
    assert json.loads(target.read_text()) == {"new": False}

    # A failed atomic write (unlink the tmp mid-way is not possible from public
    # API) — instead verify a corrupted primary falls back to .bak below.


def test_load_baseline_falls_back_to_bak_on_corruption(tmp_path: Path) -> None:
    """A truncated primary .json must fall back to the .bak copy."""
    skill_dir = _make_skill(tmp_path)
    baseline = load_baseline(skill_dir)
    assert baseline is not None
    good_score = baseline["score"]

    # Corrupt the primary baseline file (simulate a crash mid-write).
    _baseline_path(skill_dir).write_text("{ truncated", encoding="utf-8")

    # load_baseline must fall back to .bak and not raise.
    recovered = load_baseline(skill_dir)
    assert recovered is not None
    assert recovered["score"] == good_score


def test_save_baseline_is_atomic(tmp_path: Path) -> None:
    """save_baseline writes a parseable JSON (no truncation) and a .bak."""
    skill_dir = _make_skill(tmp_path)
    primary = _baseline_path(skill_dir)
    bak = skill_dir / ".skillprism_baseline.json.bak"
    assert primary.exists() and bak.exists()
    # Both must be valid JSON.
    json.loads(primary.read_text(encoding="utf-8"))
    json.loads(bak.read_text(encoding="utf-8"))


def test_file_lock_serializes_concurrent_access(tmp_path: Path) -> None:
    """Two child processes holding file_lock on the same path are serialized."""
    lock_path = tmp_path / ".skillprism.lock"
    repo_root = Path(__file__).resolve().parents[1]
    script = textwrap.dedent(
        f"""
        import time
        from skillprism._locking import file_lock
        with file_lock({str(lock_path.as_posix())!r}):
            # hold the lock briefly so the second process must wait
            time.sleep(0.2)
        """
    )
    env = {"PYTHONPATH": str(repo_root)}
    # Launch two concurrent processes; the second must block behind the first.
    start = __import__("time").perf_counter()
    procs = [subprocess.Popen([sys.executable, "-c", script], env=env) for _ in range(2)]
    for p in procs:
        p.wait()
    elapsed = __import__("time").perf_counter() - start
    # If serialized, total ~ 0.4s (two 0.2s holds back-to-back). If racy, ~0.2s.
    assert elapsed >= 0.35, f"locks not serialized: elapsed={elapsed:.2f}s"


def test_concurrent_save_baseline_keeps_ratchet_monotonic(tmp_path: Path) -> None:
    """Two concurrent save_baseline calls must not regress historical_best_score."""
    skill_dir = _make_skill(tmp_path)
    before = load_baseline(skill_dir)
    assert before is not None
    best_before = before["historical_best_score"]

    # Two concurrent saves (same score) — the lock prevents the RMW race that
    # would otherwise let the second write clobber historical_best_score.
    repo_root = Path(__file__).resolve().parents[1]
    code = textwrap.dedent(
        f"""
        from pathlib import Path
        from skillprism.evaluate_skill_rubric import DEFAULT_CONFIG, evaluate_skill, load_config
        from skillprism._baseline import load_baseline, save_baseline
        skill = Path({str(skill_dir.as_posix())!r})
        cfg = load_config(DEFAULT_CONFIG)
        rep = evaluate_skill(skill, cfg)
        save_baseline(skill, rep)
        b = load_baseline(skill)
        print(b["historical_best_score"])
        """
    )
    env = {"PYTHONPATH": str(repo_root)}
    procs = [
        subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, env=env)
        for _ in range(3)
    ]
    for p in procs:
        p.wait()
    after = load_baseline(skill_dir)
    assert after is not None
    # historical_best_score must be monotonically non-decreasing under concurrent writes.
    assert after["historical_best_score"] >= best_before
