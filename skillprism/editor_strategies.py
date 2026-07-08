#!/usr/bin/env python3
"""Per-dimension editing strategy templates for the SKILL.md auto-editor.

These strategies translate a weak rubric dimension into concrete editing
instructions for an external editor command (e.g. an LLM). They are inspired by
empirical skill-optimization workflows but remain provider-agnostic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

#: Concrete editing instructions keyed by rubric dimension code.
DIMENSION_STRATEGIES: dict[str, str] = {
    "D1": (
        "Improve structure and frontmatter metadata. Ensure the file has a valid YAML "
        "frontmatter with `name`, `description`, and `keywords`. Add or fix a clear "
        "table of contents, section headers, and consistent Markdown formatting."
    ),
    "D2": (
        "Improve documentation clarity and completeness. Add a concise 'When to Use' "
        "section, explicit Inputs/Outputs tables, a runnable Quick Start example, "
        "and a 'Common Pitfalls / Troubleshooting' section. Remove vague wording."
    ),
    "D3": (
        "Improve executability and correctness. Ensure the Quick Start example is "
        "runnable as-is, includes all necessary imports, and references actual files "
        "or commands that exist in the skill directory. Add smoke-test hints if useful."
    ),
    "D4": (
        "Improve environment reproducibility. Add a `requirements.txt` or equivalent "
        "dependency list, specify the minimum Python version, and include installation "
        "instructions. If external tools are needed, list them and how to install them."
    ),
    "D5": (
        "Improve domain accuracy. Add domain-specific references, recommended libraries, "
        "parameter guidance, and caution notes. Verify that examples match the domain "
        "idioms and that any cited resources are plausible."
    ),
    "D6": (
        "Improve LLM callability. Ensure the Inputs and Outputs sections are explicit, "
        "add example prompts the LLM can use, and avoid ambiguous instructions. Add "
        "expected return formats and boundary conditions."
    ),
    "D7": (
        "Improve performance and robustness. Add notes on expected runtime, memory usage, "
        "or limits. Include error handling guidance and what to do for large inputs."
    ),
    "D8": (
        "Improve maintainability. Add a changelog or version note, clarify authorship, "
        "and keep sections modular so future edits do not break existing examples."
    ),
    "D9": (
        "Improve security and trust. Add a 'High-Risk Action Blacklist' section that "
        "explicitly forbids dangerous commands (e.g. `rm -rf /`, `git reset --hard`, "
        "force-push). Include input validation guidance and data privacy notes."
    ),
}

#: Dimension clusters that can be improved together in one edit round.
DIMENSION_CLUSTERS: Dict[str, List[str]] = {
    "documentation_callability": ["D2", "D6"],
    "structure_dependencies": ["D1", "D4"],
}


def get_strategy(dimension_code: Optional[str], related: Optional[List[str]] = None) -> str:
    """Return the editing strategy for a dimension, or a generic fallback.

    If ``related`` dimensions are provided, include their strategies in the prompt
    so a single edit can improve a cluster of weak dimensions.
    """
    if not dimension_code:
        return (
            "Improve the SKILL.md overall: strengthen structure, examples, inputs/outputs, "
            "and domain guidance."
        )

    main_strategy = DIMENSION_STRATEGIES.get(
        dimension_code,
        f"Improve dimension {dimension_code}. Add concrete examples, remove ambiguity, "
        "and ensure the section is self-contained.",
    )

    if not related:
        return main_strategy

    related_strategies = []
    for code in related:
        if code != dimension_code and code in DIMENSION_STRATEGIES:
            related_strategies.append(f"- {code}: {DIMENSION_STRATEGIES[code]}")

    if not related_strategies:
        return main_strategy

    return (
        f"Primary focus ({dimension_code}): {main_strategy}\n\n"
        "Also address these related dimensions in the same edit:\n" + "\n".join(related_strategies)
    )


def get_dimension_clusters(config: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """Return dimension clusters from config, falling back to defaults."""
    if config and "optimization" in config:
        clusters = config["optimization"].get("clusters", [])
        if clusters:
            return {c["name"]: list(c["dimensions"]) for c in clusters if "name" in c}
    return DIMENSION_CLUSTERS


def find_related_dimensions(
    dimension_code: str,
    dimension_scores: Dict[str, int],
    config: Optional[Dict[str, Any]] = None,
    threshold: int = 3,
) -> List[str]:
    """Find related dimensions in the same cluster that are also weak."""
    clusters = get_dimension_clusters(config)
    for codes in clusters.values():
        if dimension_code in codes:
            return [
                code
                for code in codes
                if code != dimension_code and dimension_scores.get(code, 5) <= threshold
            ]
    return []
