#!/usr/bin/env python3
"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """Run every test from a temp working directory.

    The engine writes generated artifacts (history.jsonl, test-prompts.json,
    llm_judgments.json) to cwd-relative ``artifacts/<skill>/`` paths. Without
    isolation, tests that exercise real evaluation flows would litter the
    repository root with those files. Tests that genuinely need the repo root
    (subprocess CLI smoke tests) chdir back explicitly.
    """
    monkeypatch.chdir(tmp_path)
