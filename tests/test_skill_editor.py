#!/usr/bin/env python3
"""Tests for skillprism.skill_editor."""

from __future__ import annotations

from skillprism.skill_editor import SkillEditor, SkillEditorResult


def test_skill_editor_from_env_missing() -> None:
    import os

    old = os.environ.pop("SKILLPRISM_EDITOR_COMMAND", None)
    try:
        assert SkillEditor.from_env() is None
    finally:
        if old is not None:
            os.environ["SKILLPRISM_EDITOR_COMMAND"] = old


def test_skill_editor_from_config_disabled() -> None:
    assert SkillEditor.from_config({"editor": {"enabled": False}}) is None


def test_skill_editor_from_config_enabled() -> None:
    editor = SkillEditor.from_config(
        {"editor": {"enabled": True, "command": "cat", "max_retries": 1}}
    )
    assert editor is not None
    assert editor.command == "cat"
    assert editor.max_retries == 1


def test_skill_editor_is_available_with_caller() -> None:
    editor = SkillEditor(caller=lambda _: "# skill")
    assert editor.is_available() is True


def test_skill_editor_validate_rejects_empty() -> None:
    assert SkillEditor._validate("") is None
    assert SkillEditor._validate("   ") is None
    assert SkillEditor._validate("no header") is None


def test_skill_editor_validate_accepts_markdown() -> None:
    result = SkillEditor._validate("# Title\nbody")
    assert isinstance(result, SkillEditorResult)
    assert result.content == "# Title\nbody"


def test_skill_editor_edit_with_caller() -> None:
    editor = SkillEditor(caller=lambda _: "# new skill", max_retries=0)
    result = editor.edit("prompt")
    assert result is not None
    assert "# new skill" in result.content


def test_skill_editor_edit_retries_on_failure() -> None:
    calls = []

    def fail_once(_):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return "# ok"

    editor = SkillEditor(caller=fail_once, max_retries=1)
    result = editor.edit("prompt")
    assert result is not None
    assert len(calls) == 2
