#!/usr/bin/env python3
"""Optional provider-agnostic SKILL.md editor for autonomous optimization.

This module is intentionally not part of the core engine. The engine stays
LLM-free; the editor is an optional Skill-layer plugin that can call any
external command (LLM wrapper, agent tool, etc.) to rewrite SKILL.md.

Example command:
    export SKILLPRISM_EDITOR_COMMAND="python scripts/my_skill_editor.py"
    improve-skill skills/<skill> --auto-edit --apply

The command reads a prompt from stdin and should print the full updated
SKILL.md content to stdout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass
class SkillEditorResult:
    content: str


class SkillEditor:
    """External SKILL.md editor wrapper.

    The editor is defensive by default:
      - Empty responses are rejected.
      - Responses that do not contain a `#` markdown header are rejected.
      - Calls can be retried on failure.
    """

    def __init__(
        self,
        caller: Optional[Callable[[str], str]] = None,
        command: Optional[str] = None,
        max_retries: int = 2,
    ) -> None:
        self.caller = caller
        self.command = command
        self.max_retries = max(0, max_retries)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> Optional["SkillEditor"]:
        """Build a SkillEditor from the `editor` section of skill_rubric_types.yaml."""
        cfg = config.get("editor")
        if not cfg or not cfg.get("enabled"):
            return None
        return cls(
            command=cfg.get("command"),
            max_retries=int(cfg.get("max_retries", 2)),
        )

    @classmethod
    def from_env(cls) -> Optional["SkillEditor"]:
        """Build a SkillEditor from SKILLPRISM_EDITOR_COMMAND env var."""
        cmd = os.environ.get("SKILLPRISM_EDITOR_COMMAND")
        if not cmd:
            return None
        return cls(command=cmd)

    def is_available(self) -> bool:
        if self.caller is not None:
            return True
        if not self.command:
            return False
        return shutil.which(self.command.split()[0]) is not None

    def _call_subprocess(self, prompt: str) -> str:
        if not self.command:
            raise RuntimeError("No skill editor command configured")
        parts = self.command.split()
        executable = shutil.which(parts[0])
        if executable is None:
            raise RuntimeError(f"Skill editor command not found: {parts[0]}")
        proc = subprocess.run(
            [executable] + parts[1:],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Skill editor failed: {proc.stderr[:500]}")
        return proc.stdout

    def _call(self, prompt: str) -> str:
        if self.caller:
            return self.caller(prompt)
        return self._call_subprocess(prompt)

    @staticmethod
    def _validate(content: str) -> Optional[SkillEditorResult]:
        """Basic validation: must be non-empty and look like a SKILL.md."""
        stripped = content.strip()
        if not stripped:
            return None
        if "#" not in stripped:
            return None
        return SkillEditorResult(content=stripped)

    def edit(self, prompt: str) -> Optional[SkillEditorResult]:
        """Call the editor and return the validated result, or None on failure."""
        for _ in range(self.max_retries + 1):
            try:
                response = self._call(prompt)
                result = self._validate(response)
                if result is not None:
                    return result
            except Exception:
                continue
        return None


def build_editor_prompt(
    skill_path: Path,
    current_content: str,
    weakest: Optional[Dict[str, Any]],
    current_score: float,
    strategy: str = "",
    edit_code: bool = False,
    single_dimension: bool = True,
) -> str:
    """Build a focused prompt for an external SKILL.md editor."""
    lines = [
        f"You are optimizing the SKILL.md file for the skill `{skill_path.name}`.",
        f"Current rubric score: {current_score:.1f} / 100.",
        "",
    ]
    if weakest:
        lines.extend(
            [
                f"Focus on the weakest dimension: {weakest['code']} - {weakest['name']} "
                f"(score {weakest['score']}/5).",
                f"Suggestions: {'; '.join(weakest.get('suggestions') or []) or 'N/A'}",
                "",
            ]
        )
    if single_dimension:
        lines.extend(
            [
                "IMPORTANT: Edit ONLY this single dimension in this round. "
                "Do not change other dimensions. "
                "This keeps the score delta attributable to one variable.",
                "",
            ]
        )
    if strategy:
        lines.extend(
            [
                "Concrete editing strategy for this dimension:",
                strategy,
                "",
            ]
        )
    if edit_code:
        lines.extend(
            [
                "You MAY also edit code assets in addition to SKILL.md.",
                "Allowed paths: scripts/, examples/, requirements.txt, pyproject.toml, setup.py, setup.cfg, Makefile.",
                "Return the complete updated SKILL.md content as usual; apply code changes to the files directly if needed.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "ONLY edit SKILL.md. Do not modify code assets (scripts, examples, requirements.txt, etc.).",
                "",
            ]
        )
    lines.extend(
        [
            "Return the complete updated SKILL.md content (with frontmatter) as plain Markdown. "
            "Do not wrap it in code fences.",
            "",
            "Current SKILL.md:",
            "---",
            current_content[:12000],
            "---",
        ]
    )
    return "\n".join(lines)
