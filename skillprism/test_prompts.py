#!/usr/bin/env python3
"""Test prompt management for skill effect verification.

Each skill should have 2-3 representative prompts that exercise its claimed
capability. The prompts are
used by `--llm-judge` or external agents to verify dim8 "measured performance".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, cast

DEFAULT_PROMPTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "scenario": "trigger",
        "prompt": "Use this skill for its most typical task.",
        "expected": "A concise description of the expected behavior (workflow conformance, not numeric results).",
    },
    {
        "id": 2,
        "scenario": "ambiguous",
        "prompt": "Use this skill with a slightly ambiguous or complex input.",
        "expected": "The skill should ask for clarification or handle ambiguity gracefully.",
    },
]


def _read_skill_md(skill_path: Path) -> str:
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return ""
    return skill_md.read_text(encoding="utf-8", errors="replace")


def _extract_frontmatter(skill_path: Path) -> Dict[str, Any]:
    content = _read_skill_md(skill_path)
    match = re.search(r"(?m)^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        import yaml

        data = yaml.safe_load(match.group(1)) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def artifacts_dir(skill_path: Path) -> Path:
    """Default directory for generated artifacts: ``artifacts/<skill>/``.

    Relative to the current working directory (the project root), so each
    skill's generated files stay isolated and the skill source tree remains
    read-only.
    """
    return Path("artifacts") / skill_path.name


def baseline_dir(skill_path: Path) -> Path:
    """Baseline snapshot directory: ``artifacts/<skill>/baseline/``.

    Lives outside the skill source tree (previously
    ``<skill>/.skillprism_baseline.json`` and ``<skill>/.skillprism_baseline/``),
    keeping the checked-out skill repo read-only.
    """
    return artifacts_dir(skill_path) / "baseline"


def default_prompts_dir(skill_path: Path) -> Path:
    """Default directory for prompt artifacts: ``artifacts/<skill>/``.

    Pass the skill directory as ``--prompts-dir`` to opt into storing prompts
    inside the skill tree.
    """
    return artifacts_dir(skill_path)


def generate_test_prompts(skill_path: Path) -> List[Dict[str, Any]]:
    """Generate 3 template test prompts from SKILL.md content.

    Fallback only: these are generic placeholders ("Use the X skill to ...")
    without concrete inputs or verifiable expected outputs. Prefer
    agent-authored prompts created per ``references/PROMPTS_VERIFICATION.md``.

    Uses the skill name, description, and first workflow section to create:
    1. A trigger/workflow-conformance prompt
    2. An ambiguous/complex prompt
    3. A boundary/failure-mode prompt
    """
    fm = _extract_frontmatter(skill_path)
    name = fm.get("name", skill_path.name)
    description = str(fm.get("description", "")).split("\n")[0]
    content = _read_skill_md(skill_path)

    # Try to find the first concrete action in the content
    first_step = "perform its main task"
    step_match = re.search(r"(?:Step\s*1|1\.\s+)([^\n]+)", content)
    if step_match:
        first_step = step_match.group(1).strip()[:120]

    prompts = [
        {
            "id": 1,
            "scenario": "trigger",
            "prompt": f"Use the {name} skill to {first_step} under normal conditions.",
            "expected": f"The agent should follow the skill's documented workflow (tool choice, step order, output structure) for {name}; a light walkthrough on small sample data suffices — no full computation or numeric result checks required.",
        },
        {
            "id": 2,
            "scenario": "ambiguous",
            "prompt": f"Use the {name} skill with an ambiguous or incomplete request related to: {description}",
            "expected": "The skill should either ask for clarification or handle the ambiguity gracefully without making unsafe assumptions.",
        },
        {
            "id": 3,
            "scenario": "boundary",
            "prompt": f"Use the {name} skill with edge-case input (empty, malformed, or at the boundary of its stated capabilities).",
            "expected": "The skill should not crash; it should follow its failure-mode/fallback instructions if applicable.",
        },
    ]
    return prompts


def load_test_prompts(skill_path: Path, prompts_dir: Path | None = None) -> List[Dict[str, Any]]:
    """Load test prompts from ``{prompts_dir or skill_path}/test-prompts.json`` if present."""
    prompt_file = (prompts_dir or skill_path) / "test-prompts.json"
    if not prompt_file.exists():
        return []
    try:
        data = json.loads(prompt_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return cast(List[Dict[str, Any]], data)
        return cast(List[Dict[str, Any]], cast(Dict[str, Any], data).get("prompts", []))
    except Exception:
        return []


def save_test_prompts(
    skill_path: Path, prompts: List[Dict[str, Any]], output_dir: Path | None = None
) -> Path:
    """Write test prompts to ``{output_dir or skill_path}/test-prompts.json``."""
    prompt_file = (output_dir or skill_path) / "test-prompts.json"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(
        json.dumps(prompts, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return prompt_file


def ensure_test_prompts(
    skill_path: Path, auto_generate: bool = True, output_dir: Path | None = None
) -> Path:
    """Ensure a skill has test prompts, creating defaults if missing.

    If auto_generate is True, generate prompts from SKILL.md content instead of
    using generic defaults.

    If output_dir is provided, prompts are written there instead of inside the
    skill source tree, keeping evaluation read-only with respect to the skill.
    """
    existing = load_test_prompts(skill_path, prompts_dir=output_dir)
    if existing:
        return (output_dir or skill_path) / "test-prompts.json"
    prompts = generate_test_prompts(skill_path) if auto_generate else DEFAULT_PROMPTS
    return save_test_prompts(skill_path, prompts, output_dir=output_dir)


def count_test_prompts(skill_path: Path, prompts_dir: Path | None = None) -> int:
    """Return the number of test prompts for a skill."""
    return len(load_test_prompts(skill_path, prompts_dir=prompts_dir))


def format_test_prompts_report(skill_path: Path, prompts_dir: Path | None = None) -> str:
    """Return a human-readable summary of test prompts for a skill."""
    count = count_test_prompts(skill_path, prompts_dir=prompts_dir)
    if count == 0:
        return (
            "Test prompts: missing — create test-prompts.json per "
            "references/PROMPTS_VERIFICATION.md"
        )
    return f"Test prompts: {count} prompt(s) ready for effect verification"
