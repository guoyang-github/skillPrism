#!/usr/bin/env python3
"""
Skill Rubric Evaluator (Project-Agnostic, Config-Driven) v2.0

Evaluates skills using the Rubric defined in
`docs/SKILL_EVALUATION_AND_OPTIMIZATION_FRAMEWORK.md` (or equivalent documentation).

Type definitions live in `skill_rubric_types.yaml` (by default, next to this
script) and can be extended without modifying this script.

New in v2.0:
  - Configurable scoring weights and grade thresholds via YAML
  - D9 Security dimension (inspired by NVIDIA SkillSpector)
  - SkillLens 3-dimension checks (failure encoding, specificity, risk blacklist)
  - Optional smoke test and dependency reproducibility checks
  - Score history tracking (JSONL)
  - Ratchet mode: fail on regression vs previous baseline

Usage:
    # Single skill (auto-detect type)
    python evaluate_skill_rubric.py skills/bio-single-cell-clustering

    # Evaluate all skills with smoke tests and dependency checks
    python evaluate_skill_rubric.py --all --skills-dir ./skills \
        --run-smoke --run-deps --output reports/SKILL_SCORECARD.md

    # Batch with history tracking
    python evaluate_skill_rubric.py --all --skills-dir ./skills \
        --output reports/SKILL_SCORECARD.md --output-history artifacts/skill_history.jsonl

    # Ratchet mode: fail if any skill regresses from previous scorecard
    python evaluate_skill_rubric.py --all --skills-dir ./skills \
        --output reports/SKILL_SCORECARD.md --ratchet
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import yaml

from .dependency_checker import check_dependencies, format_dependency_report
from .dimensions import (
    evaluate_d1_structure,
    evaluate_d2_documentation,
    evaluate_d3_executability,
    evaluate_d4_environment,
    evaluate_d5_domain_accuracy,
    evaluate_d6_llm_callability,
    evaluate_d7_robustness,
    evaluate_d8_maintainability,
    evaluate_d9_security_dimension,
)
from .experiment_history import record_baseline
from .llm_judge import (
    LLMJudge,
    MultiJudgeResult,
    blend_score,
)
from .prompts_verification import (
    PromptsVerificationReport,
    format_prompts_verification_report,
    load_prompts_verification,
)
from .rubric_enhancements import RubricEnhancements, evaluate_all
from .runtime_neutrality import check_runtime_neutrality, format_runtime_neutrality_report
from .security_evaluator import evaluate_d9_security, format_findings
from .skill_lens_checks import evaluate_skill_lens, format_skill_lens_report
from .smoke_test_runner import format_smoke_report, run_smoke_tests
from .test_prompts import (
    default_prompts_dir,
    ensure_test_prompts,
    format_test_prompts_report,
)
from .utils import _glob_skill, _log, _read_frontmatter
from .utils import read_skill_md as _read_skill_md

__all__ = [
    "DEFAULT_CONFIG",
    "DEFAULT_GRADE_THRESHOLDS",
    "DEFAULT_WEIGHTS",
    "DimensionResult",
    "SkillReport",
    "detect_skill_type",
    "evaluate_skill",
    "format_report_markdown",
    "format_scorecard",
    "get_grade_thresholds",
    "get_weights",
    "load_config",
    "main",
    "_score_from_checks",
]

# --------------------------------------------------------------------------- #
# Defaults / constants
# --------------------------------------------------------------------------- #

DEFAULT_SKILLS_DIR = Path("./skills").resolve()
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "skill_rubric_types.yaml"

# Fallback values if YAML scoring section is missing
DEFAULT_WEIGHTS = {
    "D1": 0.10,
    "D2": 0.15,
    "D3": 0.18,
    "D4": 0.12,
    "D5": 0.15,
    "D6": 0.10,
    "D7": 0.08,
    "D8": 0.04,
    "D9": 0.08,
}
DEFAULT_GRADE_THRESHOLDS = {"A": 90, "B": 75, "C": 60}


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass
class DimensionResult:
    code: str
    name: str
    score: int  # 1-5
    max_score: int = 5
    evidence: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    total_checks: int = 0
    skipped_checks: int = 0


@dataclass
class SkillReport:
    name: str
    path: Path
    skill_type: str
    dimensions: List[DimensionResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    smoke_report: Optional[str] = None
    dependency_report: Optional[str] = None
    security_findings: Optional[str] = None
    skill_lens_report: Optional[str] = None
    runtime_neutrality_report: Optional[str] = None
    test_prompts_report: Optional[str] = None
    llm_judgments_report: Optional[str] = None
    prompts_verification_report: Optional[str] = None
    llm_judgments: Dict[str, MultiJudgeResult] = field(default_factory=dict)
    prompts_verification: Optional[PromptsVerificationReport] = None
    enhancements: Optional[RubricEnhancements] = None

    def total_weighted(self, weights: Optional[Dict[str, float]] = None) -> float:
        w = weights or DEFAULT_WEIGHTS
        total = sum(d.score * w.get(d.code, 0.0) for d in self.dimensions)
        return total / 5.0 * 100.0

    def fused_score(
        self,
        weights: Optional[Dict[str, float]] = None,
        llm_effect_weight: float = 0.0,
    ) -> float:
        # LLM effect testing is intentionally outside the engine (skill-driven).
        # The parameter is kept for backward compatibility but ignored.
        return self.total_weighted(weights)

    def grade(
        self, score: Optional[float] = None, thresholds: Optional[Dict[str, int]] = None
    ) -> str:
        s = score if score is not None else self.total_weighted()
        t = thresholds or DEFAULT_GRADE_THRESHOLDS
        if s >= t.get("A", 90):
            return "A"
        if s >= t.get("B", 75):
            return "B"
        if s >= t.get("C", 60):
            return "C"
        return "D"

    def check_counts(self) -> Dict[str, int]:
        """Aggregate total/skipped checks across all dimensions."""
        return {
            "total": sum(d.total_checks for d in self.dimensions),
            "skipped": sum(d.skipped_checks for d in self.dimensions),
        }

    def dry_run_ratio(self) -> float:
        counts = self.check_counts()
        total = counts["total"]
        return counts["skipped"] / total if total else 0.0


# --------------------------------------------------------------------------- #
# Configuration loading
# --------------------------------------------------------------------------- #


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        config = cast(Dict[str, Any], yaml.safe_load(f) or {})
    # Validate shape so YAML typos (e.g. 'wieghts:') surface instead of
    # silently falling back to defaults.
    from .config_schema import validate_config

    return validate_config(config)


def get_scoring_config(config: Dict[str, Any]) -> Dict[str, Any]:
    return cast(Dict[str, Any], config.get("scoring", {}))


def get_weights(config: Dict[str, Any]) -> Dict[str, float]:
    cfg = get_scoring_config(config)
    weights = cast(Dict[str, float], cfg.get("weights", DEFAULT_WEIGHTS))
    # Sanity-check the weight sum: a typo'd config could otherwise push scores
    # above 100. Warn and renormalize rather than fail hard (engine stays usable).
    total = sum(float(w) for w in weights.values())
    if total > 0 and abs(total - 1.0) > 0.02:
        print(
            f"Warning: dimension weights sum to {total:.4f}, expected ~1.0; "
            "renormalizing. Fix skill_rubric_types.yaml scoring.weights."
        )
        weights = {k: float(w) / total for k, w in weights.items()}
    return weights


def get_grade_thresholds(config: Dict[str, Any]) -> Dict[str, int]:
    cfg = get_scoring_config(config)
    return cast(Dict[str, int], cfg.get("grade_thresholds", DEFAULT_GRADE_THRESHOLDS))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _score_from_checks(checks: List[Tuple[bool, str, str]]) -> DimensionResult:
    """Map a list of (passed, evidence, suggestion) tuples to a 1-5 score.

    Skipped checks (e.g. "shellcheck not installed; skipped") are excluded from
    both the numerator and the denominator, so an incomplete environment does
    not inflate the score.
    """
    from .utils import _is_skipped_message

    evidence: List[str] = []
    suggestions: List[str] = []
    skipped = 0
    for ok, good_msg, bad_msg in checks:
        msg = good_msg if ok else bad_msg
        if ok and _is_skipped_message(msg):
            skipped += 1
            continue  # skipped checks do not count toward passed or total
        (evidence if ok else suggestions).append(msg)

    real_passed = sum(1 for ok, _, _ in checks if ok) - skipped
    n = len(checks) - skipped
    ratio = (real_passed / n) if n else 0
    if ratio >= 0.9:
        score = 5
    elif ratio >= 0.7:
        score = 4
    elif ratio >= 0.5:
        score = 3
    elif ratio >= 0.3:
        score = 2
    else:
        score = 1
    return DimensionResult(
        code="",
        name="",
        score=score,
        evidence=evidence,
        suggestions=suggestions,
        total_checks=len(checks),
        skipped_checks=skipped,
    )


# Shared helpers above are imported from ``skillprism.utils`` to avoid copy
# drift and circular imports between the orchestrator and dimension modules.


# --------------------------------------------------------------------------- #
# Type detection
# --------------------------------------------------------------------------- #


def detect_skill_type(skill_path: Path, config: Dict[str, Any]) -> str:
    frontmatter, _ = _read_frontmatter(skill_path)
    name = str(frontmatter.get("name", skill_path.name)).lower()
    description = str(frontmatter.get("description", "")).lower()
    tool_type = str(frontmatter.get("tool_type", "")).lower()
    text = f"{name} {description} {tool_type}"

    types = config.get("skill_types", {})
    scores: Dict[str, int] = {t: 0 for t in types if t != "generic"}

    for type_key, type_cfg in types.items():
        if type_key == "generic":
            continue
        detection = type_cfg.get("detection", {})

        if tool_type and tool_type in [t.lower() for t in detection.get("tool_type", [])]:
            scores[type_key] += 10

        for hint in detection.get("keywords", []):
            if hint.lower() in text:
                scores[type_key] += 1

        for pattern in detection.get("file_patterns", []):
            if _glob_skill(skill_path, pattern):
                scores[type_key] += 2

    if scores:
        best = max(scores, key=lambda k: scores[k])
        if scores[best] > 0:
            return best

    return "generic"


# --------------------------------------------------------------------------- #
# Dimension evaluators
# --------------------------------------------------------------------------- #


BUILTIN_DIMENSION_EVALUATORS: Dict[str, Callable[..., "DimensionResult"]] = {
    "D1": evaluate_d1_structure,
    "D2": evaluate_d2_documentation,
    "D3": evaluate_d3_executability,
    "D4": evaluate_d4_environment,
    "D5": evaluate_d5_domain_accuracy,
    "D6": evaluate_d6_llm_callability,
    "D7": evaluate_d7_robustness,
    "D8": evaluate_d8_maintainability,
    "D9": evaluate_d9_security_dimension,
}


def get_dimension_evaluators(
    config: Dict[str, Any], skill_type: str
) -> List[Callable[..., "DimensionResult"]]:
    """Return ordered dimension evaluators for a skill type.

    If ``enabled_dimensions`` is configured for the skill type, only those
    dimensions are evaluated. Unknown codes are warned and skipped.
    """
    type_cfg = config.get("skill_types", {}).get(skill_type, {})
    enabled = type_cfg.get("enabled_dimensions")
    if enabled is None:
        return list(BUILTIN_DIMENSION_EVALUATORS.values())

    evaluators: List[Callable[..., "DimensionResult"]] = []
    for code in enabled:
        evaluator = BUILTIN_DIMENSION_EVALUATORS.get(code)
        if evaluator is None:
            print(
                f"Warning: enabled_dimensions contains unknown dimension '{code}' for "
                f"skill type '{skill_type}'; skipping.",
                file=sys.stderr,
            )
            continue
        evaluators.append(evaluator)
    return evaluators


def evaluate_skill(
    skill_path: Path,
    config: Dict[str, Any],
    skill_type: Optional[str] = None,
    verbose: bool = False,
    run_smoke: bool = False,
    run_deps: bool = False,
    allow_exec: bool = False,
    llm_judge: Optional[LLMJudge] = None,
    llm_judgments: Optional[Dict[str, MultiJudgeResult]] = None,
    prompts_verification: Optional[PromptsVerificationReport] = None,
    auto_generate_prompts: bool = True,
    prompts_dir: Optional[Path] = None,
) -> SkillReport:
    if not skill_path.is_dir():
        report = SkillReport(
            name=skill_path.name, path=skill_path, skill_type=skill_type or "unknown"
        )
        report.errors.append("Not a directory")
        return report

    detected_type = skill_type or detect_skill_type(skill_path, config)
    report = SkillReport(name=skill_path.name, path=skill_path, skill_type=detected_type)
    _log(f"  detected type: {detected_type}", verbose)

    for evaluator in get_dimension_evaluators(config, detected_type):
        try:
            dim = evaluator(skill_path, detected_type, config, verbose=verbose, llm_judge=llm_judge)
            report.dimensions.append(dim)
        except Exception as e:
            # Insert a score=1 placeholder so total_weighted keeps a consistent
            # denominator (otherwise a crashed dimension silently drops the max
            # achievable score by its weight). The real failure is also logged.
            code_match = re.search(r"d(\d+)", evaluator.__name__)
            code = f"D{code_match.group(1)}" if code_match else evaluator.__name__
            report.dimensions.append(
                DimensionResult(
                    code=code,
                    name=evaluator.__name__,
                    score=1,
                    evidence=[],
                    suggestions=[f"evaluator failed: {e}"],
                )
            )
            report.errors.append(f"{evaluator.__name__} failed: {e}")

    # Attach detailed security findings to the report so users can see the raw scan.
    try:
        _, _, _, findings = evaluate_d9_security(skill_path, detected_type, config)
        report.security_findings = format_findings(findings)
    except Exception as e:
        report.errors.append(f"security findings failed: {e}")

    # Apply pre-computed multi-judge LLM judgments if provided; otherwise
    # auto-discover ``artifacts/<skill>/llm_judgments.json`` (relative to the
    # current working directory).
    if llm_judgments is None:
        auto_judgments_path = default_prompts_dir(skill_path) / "llm_judgments.json"
        if auto_judgments_path.exists():
            llm_judgments = _load_llm_judgments(str(auto_judgments_path))
    if llm_judgments:
        report.llm_judgments = llm_judgments
        for dim in report.dimensions:
            judgment = llm_judgments.get(dim.code)
            if judgment and dim.code in ("D2", "D5", "D6", "D8"):
                llm_judge_cfg = config.get("llm_judge", {})
                weight = float(llm_judge_cfg.get("weight", 0.3)) if llm_judge_cfg else 0.3
                blended = blend_score(dim.score, judgment.aggregated_score, weight)
                dim.evidence.append(
                    f"LLM judges: {judgment.scores} (aggregate={judgment.aggregate}, "
                    f"score={judgment.aggregated_score}) blended to {blended}/5"
                )
                dim.score = blended

    # Apply pre-computed prompts verification if provided; otherwise auto-discover
    # the per-skill default ``artifacts/<skill>/prompts_verification.json``
    # (relative to the current working directory).
    if prompts_verification is None:
        prompts_verification = load_prompts_verification(
            default_prompts_dir(skill_path) / "prompts_verification.json"
        )
    if prompts_verification:
        report.prompts_verification = prompts_verification
        report.prompts_verification_report = format_prompts_verification_report(
            prompts_verification
        )
        for dim in report.dimensions:
            if dim.code in ("D6", "D8"):
                pass_rate = prompts_verification.pass_rate
                dim.evidence.append(f"Test-prompts verification pass rate: {pass_rate:.0%}")
                if pass_rate < 0.5:
                    dim.score = max(1, dim.score - 1)
                elif pass_rate >= 0.9:
                    dim.score = min(5, dim.score + 1)

    # Rubric enhancements (SkillLens-inspired rule-based checks)
    try:
        fm, _ = _read_frontmatter(skill_path)
        content = _read_skill_md(skill_path)
        enhancements = evaluate_all(
            skill_path,
            content,
            name=str(fm.get("name", skill_path.name)),
            description=str(fm.get("description", "")),
        )
        report.enhancements = enhancements
        penalty = enhancements.score_penalty()
        # Apply penalty proportionally across dimensions, capped per dim
        if penalty > 0 and report.dimensions:
            per_dim = max(1, penalty // len(report.dimensions))
            for dim in report.dimensions:
                if any(issue.check == dim.code for issue in enhancements.issues):
                    dim.score = max(1, dim.score - per_dim)
                    dim.evidence.append(
                        f"Rubric enhancement penalty: -{per_dim} (quality issues detected)"
                    )
    except Exception as e:
        report.errors.append(f"rubric enhancements failed: {e}")

    # Optional smoke tests
    if run_smoke:
        try:
            if verbose:
                _log(f"  running smoke tests for {skill_path.name}...", verbose)
            smoke = run_smoke_tests(
                skill_path, detected_type, config, verbose=verbose, allow_exec=allow_exec
            )
            report.smoke_report = format_smoke_report(smoke)
        except Exception as e:
            report.errors.append(f"smoke test failed: {e}")

    # Optional dependency checks
    if run_deps:
        try:
            if verbose:
                _log(f"  running dependency checks for {skill_path.name}...", verbose)
            deps = check_dependencies(skill_path, detected_type, config, run_dry_run=True)
            report.dependency_report = format_dependency_report(deps)
        except Exception as e:
            report.errors.append(f"dependency check failed: {e}")

    # SkillLens report (always generated, lightweight)
    try:
        lens = evaluate_skill_lens(skill_path)
        report.skill_lens_report = format_skill_lens_report(lens)
    except Exception as e:
        report.errors.append(f"SkillLens check failed: {e}")

    # Runtime neutrality check (always generated, lightweight)
    try:
        runtime_report = check_runtime_neutrality(skill_path)
        report.runtime_neutrality_report = format_runtime_neutrality_report(runtime_report)
    except Exception as e:
        report.errors.append(f"Runtime neutrality check failed: {e}")

    # Test prompts summary (always generated, lightweight). ``prompts_dir`` decouples
    # where test-prompts.json lives from the --output report path; it defaults to
    # ``artifacts/<skill>/`` so the skill source tree stays read-only.
    try:
        prompts_dir = prompts_dir or default_prompts_dir(skill_path)
        prompt_file = prompts_dir / "test-prompts.json"
        existed = prompt_file.exists()
        if auto_generate_prompts:
            ensure_test_prompts(skill_path, auto_generate=True, output_dir=prompts_dir)
        report.test_prompts_report = format_test_prompts_report(skill_path, prompts_dir=prompts_dir)
        if auto_generate_prompts and not existed and prompt_file.exists():
            report.test_prompts_report += (
                "\n⚠️ Auto-generated template prompts are placeholders only. "
                "Have the agent author real prompts per references/PROMPTS_VERIFICATION.md."
            )
    except Exception as e:
        report.errors.append(f"Test prompts check failed: {e}")

    # Record baseline in experiment history
    try:
        score = report.total_weighted(get_weights(config))
        record_baseline(skill_path, score, note="baseline evaluation", eval_mode="static")
    except Exception:
        pass

    return report


# Reporting helpers are imported here (after SkillReport / get_weights are
# defined) so ``skillprism.reports`` can import them without circularity.
from .reports import (  # noqa: E402
    _load_baseline_scores,
    format_report_markdown,
    format_scorecard,
    write_history,
)

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_evaluate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a skill's SKILL.md quality.")
    parser.add_argument("skill", nargs="?", help="Path to a single skill directory")
    parser.add_argument("--all", action="store_true", help="Evaluate all skills under --skills-dir")
    parser.add_argument(
        "--skills-dir",
        default=str(DEFAULT_SKILLS_DIR),
        help="Directory containing skill subdirectories (default: ./skills)",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to skill type configuration YAML (default: skill_rubric_types.yaml next to this script)",
    )
    parser.add_argument("--type", help="Force skill type (overrides auto-detection)")
    parser.add_argument("--output", "-o", help="Output file for scorecard (markdown)")
    parser.add_argument(
        "--detailed", action="store_true", help="Output detailed per-dimension evidence"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress")
    parser.add_argument("--run-smoke", action="store_true", help="Run smoke tests")
    parser.add_argument(
        "--allow-exec",
        action="store_true",
        help=(
            "Allow executing skill-shipped example code during smoke tests. "
            "Execution is sandboxed (rlimits + minimal env + timeout), so this "
            "is safe to enable for trusted/internal skills to get the real D3 "
            "executability signal. Keep it off for untrusted skill sources."
        ),
    )
    parser.add_argument("--run-deps", action="store_true", help="Run dependency dry-run checks")
    parser.add_argument(
        "--output-history", help="Append evaluation records to JSONL file for trend tracking"
    )
    parser.add_argument(
        "--ratchet", action="store_true", help="Fail if any skill regresses vs baseline scorecard"
    )
    parser.add_argument(
        "--ratchet-baseline",
        help="Baseline scorecard markdown for ratchet (default: --output file)",
    )
    parser.add_argument(
        "--llm-judge", action="store_true", help="Enable optional LLM-as-judge for D2/D5"
    )
    parser.add_argument(
        "--llm-judge-command", help="Command to call LLM judge (overrides env/config)"
    )
    parser.add_argument(
        "--llm-judge-weight",
        type=float,
        default=0.3,
        help="Weight of LLM score when blending (0-1)",
    )
    parser.add_argument(
        "--llm-judge-count",
        type=int,
        default=2,
        help="Number of independent LLM judges (default: 2)",
    )
    parser.add_argument(
        "--llm-judge-aggregate",
        choices=["median", "mean", "min", "max"],
        default="median",
        help="Aggregation method for multiple judges (default: median)",
    )
    parser.add_argument(
        "--llm-judgments",
        help="Path to pre-computed llm_judgments.json "
        "(default: artifacts/<skill>/llm_judgments.json)",
    )
    parser.add_argument(
        "--prompts-verification",
        help="Path to prompts verification JSON "
        "(default: artifacts/<skill>/prompts_verification.json)",
    )
    parser.add_argument(
        "--no-generate-prompts",
        action="store_true",
        help="Do not auto-generate test-prompts.json if missing",
    )
    parser.add_argument(
        "--prompts-dir",
        help="Directory to read/write test-prompts.json "
        "(default: artifacts/<skill>/ under the project root). "
        "Pass the skill directory explicitly to store prompts in the skill tree.",
    )
    return parser


def _resolve_llm_judge(args: argparse.Namespace, config: Dict[str, Any]) -> Optional[LLMJudge]:
    """Build an LLM judge from CLI args, env, or config."""
    if not args.llm_judge:
        return None
    llm_judge = LLMJudge.from_config(config) or LLMJudge.from_env()
    if args.llm_judge_command:
        llm_judge = LLMJudge(command=args.llm_judge_command.split(), weight=args.llm_judge_weight)
    elif llm_judge is not None:
        llm_judge.weight = args.llm_judge_weight
    if llm_judge is None or not llm_judge.is_available():
        print("Warning: --llm-judge requested but no LLM judge command configured.")
        print("Set SKILLPRISM_LLM_JUDGE_COMMAND or add llm_judge.command to the config.")
        return None
    llm_judge.n_judges = args.llm_judge_count
    llm_judge.aggregate = args.llm_judge_aggregate
    return llm_judge


def _load_llm_judgments(path: Optional[str]) -> Optional[Dict[str, MultiJudgeResult]]:
    """Load pre-computed LLM judgments from a JSON file."""
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {j["dimension"]: MultiJudgeResult(**j) for j in data.get("judges", [])}
    except Exception as e:
        print(f"Warning: failed to load LLM judgments: {e}")
        return None


def _resolve_skill_paths(args: argparse.Namespace, cwd: Path) -> List[Path]:
    """Return the list of skill paths to evaluate."""
    if args.all:
        skills_dir = Path(args.skills_dir)
        if not skills_dir.is_absolute():
            skills_dir = cwd / skills_dir
        # ``skill-prism`` is the meta-skill (agent harness), not a skill under test;
        # skip it when batch-evaluating a skills directory.
        return sorted(
            p
            for p in skills_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".") and p.name != "skill-prism"
        )
    p = Path(args.skill)
    if not p.is_absolute():
        p = cwd / p
    return [p]


def _run_evaluations(
    skill_paths: List[Path],
    config: Dict[str, Any],
    args: argparse.Namespace,
    llm_judge: Optional[LLMJudge],
    llm_judgments: Optional[Dict[str, MultiJudgeResult]],
    prompts_verification: Optional[PromptsVerificationReport],
) -> List[SkillReport]:
    """Evaluate all requested skills and return their reports."""
    prompts_dir: Optional[Path] = None
    if args.prompts_dir:
        prompts_dir = Path(args.prompts_dir)
        if not prompts_dir.is_absolute():
            prompts_dir = Path.cwd() / prompts_dir

    reports: List[SkillReport] = []
    for sp in skill_paths:
        _log(f"Evaluating {sp.name}...", args.verbose)
        # With --all, keep each skill's prompts in its own subdirectory so
        # multiple skills do not overwrite each other's test-prompts.json.
        per_skill_dir = (
            prompts_dir / sp.name if prompts_dir and len(skill_paths) > 1 else prompts_dir
        )
        report = evaluate_skill(
            sp,
            config,
            skill_type=args.type,
            verbose=args.verbose,
            run_smoke=args.run_smoke,
            run_deps=args.run_deps,
            allow_exec=args.allow_exec,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
            prompts_verification=prompts_verification,
            auto_generate_prompts=not args.no_generate_prompts,
            prompts_dir=per_skill_dir,
        )
        reports.append(report)
    return reports


def _write_evaluation_outputs(
    reports: List[SkillReport],
    args: argparse.Namespace,
    cwd: Path,
    config: Dict[str, Any],
) -> None:
    """Write scorecard, history, and terminal output."""
    if args.all and args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = cwd / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(format_scorecard(reports, config), encoding="utf-8")
        print(f"Scorecard written to {out_path}")
    elif len(reports) == 1:
        print(format_report_markdown(reports[0], cwd, config, detailed=args.detailed))
    else:
        print(format_scorecard(reports, config))

    if args.output_history:
        history_path = Path(args.output_history)
        if not history_path.is_absolute():
            history_path = cwd / history_path
        history_path.parent.mkdir(parents=True, exist_ok=True)
        write_history(reports, config, history_path, extra={"cli_args": vars(args)})
        print(f"History appended to {history_path}")


def _check_ratchet(
    reports: List[SkillReport],
    args: argparse.Namespace,
    cwd: Path,
    config: Dict[str, Any],
) -> int:
    """Return 1 if any skill regresses vs baseline, 0 otherwise."""
    baseline_path = Path(args.ratchet_baseline) if args.ratchet_baseline else None
    if baseline_path is None and args.output:
        baseline_path = Path(args.output)
    if baseline_path is None:
        print("Error: --ratchet requires --output or --ratchet-baseline")
        return 2
    if not baseline_path.is_absolute():
        baseline_path = cwd / baseline_path

    baseline_scores = _load_baseline_scores(baseline_path)
    regressions: List[str] = []
    for r in reports:
        current_score = r.total_weighted(get_weights(config))
        prev_score = baseline_scores.get(r.name)
        if prev_score is not None and current_score < prev_score - 0.01:
            regressions.append(f"{r.name}: {current_score:.1f} < previous {prev_score:.1f}")
    if regressions:
        print("\nRatchet failed: regressions detected")
        for line in regressions:
            print(f"  - {line}")
        return 1
    print("\nRatchet passed: no regressions detected")
    return 0


def main() -> int:
    parser = _build_evaluate_parser()
    args = parser.parse_args()

    if not args.skill and not args.all:
        parser.print_help()
        return 2

    config = load_config(Path(args.config))
    llm_judge = _resolve_llm_judge(args, config)
    llm_judgments = _load_llm_judgments(args.llm_judgments)
    prompts_verification = (
        load_prompts_verification(Path(args.prompts_verification))
        if args.prompts_verification
        else None
    )

    cwd = Path.cwd()
    skill_paths = _resolve_skill_paths(args, cwd)
    reports = _run_evaluations(
        skill_paths, config, args, llm_judge, llm_judgments, prompts_verification
    )
    _write_evaluation_outputs(reports, args, cwd, config)

    if args.ratchet:
        return _check_ratchet(reports, args, cwd, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
