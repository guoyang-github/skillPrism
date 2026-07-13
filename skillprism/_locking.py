#!/usr/bin/env python3
"""Atomic file writes and advisory locking for optimizer state files.

``.skillprism_baseline.json`` and ``history.jsonl`` were previously
written with ``Path.write_text`` (truncate-then-write), so a crash mid-write
left a truncated file that crashed every subsequent ``--judge`` / ``--auto-edit``
run via ``JSONDecodeError``. Concurrent optimizers (CI + local dev) could also
race the ``historical_best_score`` read-modify-write and silently regress the
ratchet.

``atomic_write_text`` writes to a temp file then ``os.replace`` (atomic on the
same filesystem) with an ``fsync``. ``file_lock`` provides an flock-based
advisory mutex over a ``.lock`` sidecar file.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator


def atomic_write_text(path: Path, data: str, encoding: str = "utf-8") -> None:
    """Write ``data`` to ``path`` atomically: temp file + fsync + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup of the temp file on failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


@contextmanager
def file_lock(lock_path: Path) -> Iterator[IO[str]]:
    """Advisory flock over ``lock_path``. Blocks until the lock is acquired.

    On non-Unix platforms where ``fcntl`` is unavailable, degrades to a no-op
    (the atomic-write guarantees still hold; only mutual exclusion is relaxed).
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+")
    try:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except ImportError:  # pragma: no cover - non-Unix
            pass
        yield fh
    finally:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except ImportError:  # pragma: no cover
            pass
        fh.close()


def prune_rolling_backups(directory: Path, pattern: str, keep: int = 5) -> None:
    """Keep only the ``keep`` most-recent files matching ``pattern`` in ``directory``."""
    if not directory.is_dir():
        return
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in files[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass
