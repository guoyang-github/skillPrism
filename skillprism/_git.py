#!/usr/bin/env python3
"""Git helpers for skillPrism optimization workflows."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_available(skill_path: Path) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(skill_path), "rev-parse", "--git-dir"],
            check=True,
            capture_output=True,
        )
        return True
    except Exception:
        return False


def git_commit(skill_path: Path, message: str) -> None:
    subprocess.run(
        ["git", "-C", str(skill_path), "add", "SKILL.md"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(skill_path), "commit", "-m", message],
        check=True,
        capture_output=True,
    )


def git_checkout_new_branch(skill_path: Path, branch_name: str) -> str:
    """Create a new branch, appending -2/-3 if the name exists."""
    name = branch_name
    for suffix in ["", "-2", "-3", "-4", "-5"]:
        candidate = f"{name}{suffix}" if suffix else name
        try:
            subprocess.run(
                ["git", "-C", str(skill_path), "rev-parse", "--verify", candidate],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            # Branch does not exist; create it
            subprocess.run(
                ["git", "-C", str(skill_path), "checkout", "-b", candidate],
                check=True,
                capture_output=True,
            )
            return candidate
    raise RuntimeError(f"Could not create a unique branch from {branch_name}")


def git_revert(skill_path: Path) -> None:
    """Discard the uncommitted candidate edit, restoring SKILL.md to HEAD.

    The candidate edit produced by the editor is never committed before judging
    (it is committed only in the KEEP branch). ``git revert HEAD`` is therefore
    wrong here: it would synthesize a new commit undoing the *previous* baseline
    commit, silently moving the repo to a state older than the baseline. The
    correct primitive is to discard the uncommitted working-tree (and index)
    changes for SKILL.md, restoring it to HEAD.
    """
    subprocess.run(
        ["git", "-C", str(skill_path), "checkout", "HEAD", "--", "SKILL.md"],
        check=True,
        capture_output=True,
    )


def git_show_head(skill_path: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(skill_path), "show", "HEAD:SKILL.md"],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout
    except Exception:
        return ""


def git_diff(skill_path: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(skill_path), "diff", "HEAD~1", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout
    except Exception:
        return "(diff unavailable)"


def ensure_git_ready(skill_path: Path) -> bool:
    """Ensure the skill directory is in a git repo; auto-init if needed.

    Returns True if git is available, False otherwise.
    """
    try:
        subprocess.run(
            ["git", "-C", str(skill_path), "rev-parse", "--git-dir"],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        print(f"{skill_path} is not in a git repository; initializing one.")
        try:
            subprocess.run(
                ["git", "-C", str(skill_path), "init"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(skill_path), "add", "."],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(skill_path), "commit", "-m", "Initial commit"],
                check=False,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            print("Warning: git init failed; will use file-based backup.")
            return False
    except FileNotFoundError:
        print("Warning: git not found; will use file-based backup.")
        return False
