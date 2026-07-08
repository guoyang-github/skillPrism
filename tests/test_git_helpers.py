#!/usr/bin/env python3
"""Tests for skillprism._git helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from skillprism._git import (
    ensure_git_ready,
    git_available,
    git_commit,
    git_revert,
    git_show_head,
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "-C", str(path), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True, capture_output=True
    )


def test_git_available_in_bare_directory(tmp_path: Path) -> None:
    assert not git_available(tmp_path)


def test_ensure_git_ready_initializes_repo(tmp_path: Path) -> None:
    assert ensure_git_ready(tmp_path) is True
    assert git_available(tmp_path)


def test_git_commit_and_revert(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("v1", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "initial"], check=True, capture_output=True
    )

    skill_md.write_text("v2", encoding="utf-8")
    git_commit(tmp_path, "candidate")
    assert "v2" in git_show_head(tmp_path)

    skill_md.write_text("v3", encoding="utf-8")
    git_revert(tmp_path)
    assert skill_md.read_text(encoding="utf-8") == "v2"
