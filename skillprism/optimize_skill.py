#!/usr/bin/env python3
"""
Skill improvement library / CLI.

This module does NOT call an LLM directly. It provides measurement and
accept/revert primitives so that an external agent can edit SKILL.md and then
ask skillPrism to judge the result.

Agent-facing workflow (driven by skills/skill-prism/SKILL.md):

  1. Record baseline:
       improve-skill skills/<skill> --record-baseline

  2. Get improvement guidance:
       improve-skill skills/<skill> --suggest

  3. Agent edits SKILL.md using its own LLM.

  4. Judge the edit:
       improve-skill skills/<skill> --judge [--benchmark-registry ...]
     - Keeps the edit if Rubric score improved (or benchmark improved while
       Rubric did not regress).
     - Otherwise reverts SKILL.md to the last committed/saved version.

  5. Repeat 2-4 until satisfied.

Non-Agent usage with an external LLM editor:
    export SKILLPRISM_EDITOR_COMMAND="python scripts/my_skill_editor.py"
    improve-skill skills/<skill> --auto-edit --apply --max-rounds 3

Design rationale:
  - The engine stays provider-agnostic and testable.
  - The agent owns the LLM.
  - The engine owns objective measurement, regression gating, and rollback.
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from ._baseline import (
    BASELINE_DIR,
    clear_baseline,
    load_baseline,
    load_baseline_skill_md,
    restore_code_assets,
    save_baseline,
    snapshot_code_assets,
)
from ._git import (
    ensure_git_ready,
    git_available,
    git_commit,
    git_revert,
)
from ._locking import file_lock
from .benchmark.runner import run_benchmarks
from .dimension_clusters import format_cluster_analysis
from .editor_strategies import find_related_dimensions, get_strategy
from .evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    DimensionResult,
    SkillReport,
    detect_skill_type,
    evaluate_skill,
    get_weights,
    load_config,
)
from .experiment_history import format_history_table, load_history, record_attempt
from .llm_judge import LLMJudge, MultiJudgeResult
from .optimization_strategy import format_strategies, get_strategies
from .optimizer_guards import GuardViolation, format_violations, run_guards
from .rubric_enhancements import check_bloat, check_failure_mode_encoding
from .skill_editor import SkillEditor, build_editor_prompt
from .smoke_test_runner import run_smoke_tests
from .utils import read_skill_md as _read_skill_md

# --------------------------------------------------------------------------- #
# Skill file helpers
# --------------------------------------------------------------------------- #


def load_skill_md(skill_path: Path) -> str:
    skill_md_path = skill_path / "SKILL.md"
    if not skill_md_path.exists():
        raise FileNotFoundError(f"{skill_md_path} not found")
    return skill_md_path.read_text(encoding="utf-8", errors="replace")


def save_skill_md(skill_path: Path, content: str) -> None:
    skill_md_path = skill_path / "SKILL.md"
    skill_md_path.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Benchmark helpers
# --------------------------------------------------------------------------- #


def _find_skill_code(skill_path: Path, code_path: Optional[Path] = None) -> Optional[Path]:
    if code_path:
        return code_path

    candidates = [skill_path / "examples" / "minimal_example.py"]
    scripts_dir = skill_path / "scripts" / "python"
    if scripts_dir.exists():
        candidates.extend(sorted(scripts_dir.glob("*.py")))

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def run_skill_benchmark(
    skill_path: Path,
    skill_type: Optional[str],
    registry_path: Path,
    output_dir: Optional[Path] = None,
    code_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    if not skill_type:
        return None
    out_dir = output_dir or Path("benchmarks/latest")
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_output = out_dir / f"{skill_path.name}.yaml"
    detected_code = _find_skill_code(skill_path, code_path)
    try:
        return run_benchmarks(skill_type, registry_path, detected_code, latest_output)
    except Exception as exc:
        return {"_all_pass": False, "benchmarks": {}, "error": str(exc)}


def _format_benchmark_summary(results: Optional[Dict[str, Any]]) -> str:
    if not results:
        return "No benchmark run."
    lines = [f"Overall pass: {results.get('_all_pass', False)}"]
    for bench_id, bench in results.get("benchmarks", {}).items():
        status = "PASS" if bench.get("_all_pass") else "FAIL"
        lines.append(f"  {bench_id}: {status}")
        if "error" in bench:
            lines.append(f"    error: {bench['error']}")
    return "\n".join(lines)


def benchmark_acceptable(
    old: Optional[Dict[str, Any]],
    new: Optional[Dict[str, Any]],
) -> Tuple[bool, str]:
    if not old or not new:
        return True, "no benchmark data"

    old_benchmarks = old.get("benchmarks", {})
    new_benchmarks = new.get("benchmarks", {})

    for bench_id in old_benchmarks:
        if bench_id not in new_benchmarks:
            return False, f"benchmark {bench_id} missing"

    for bench_id, old_bench in old_benchmarks.items():
        new_bench = new_benchmarks[bench_id]
        old_pass = old_bench.get("_all_pass", False)
        new_pass = new_bench.get("_all_pass", False)

        if old_pass and not new_pass:
            return False, f"benchmark {bench_id} regressed from PASS to FAIL"

        if not old_pass and not new_pass:
            old_ok = sum(1 for v in old_bench.get("_metric_pass", {}).values() if v)
            new_ok = sum(1 for v in new_bench.get("_metric_pass", {}).values() if v)
            if new_ok < old_ok:
                return False, f"benchmark {bench_id} fewer passing metrics"

        old_err = old_bench.get("error")
        new_err = new_bench.get("error")
        if not old_err and new_err:
            return False, f"benchmark {bench_id} newly errored"

    return True, "benchmark acceptable"


def benchmark_improved(
    old: Optional[Dict[str, Any]],
    new: Optional[Dict[str, Any]],
) -> bool:
    if not old or not new:
        return False
    improved = False
    for bench_id, old_bench in old.get("benchmarks", {}).items():
        if bench_id not in new.get("benchmarks", {}):
            continue
        new_bench = new["benchmarks"][bench_id]
        old_pass = old_bench.get("_all_pass", False)
        new_pass = new_bench.get("_all_pass", False)
        if (not old_pass) and new_pass:
            improved = True
            continue
        if not old_pass and not new_pass:
            old_ok = sum(1 for v in old_bench.get("_metric_pass", {}).values() if v)
            new_ok = sum(1 for v in new_bench.get("_metric_pass", {}).values() if v)
            if new_ok > old_ok:
                improved = True
    return improved


# --------------------------------------------------------------------------- #
# Evaluation helpers
# --------------------------------------------------------------------------- #


def display_score(report: SkillReport, config: Dict[str, Any]) -> Tuple[float, str]:
    weights = get_weights(config)
    score = report.fused_score(weights, 0.0)
    grade = report.grade(score, config.get("scoring", {}).get("grade_thresholds", {}))
    return score, grade


def find_weakest_dimension(report: SkillReport) -> Optional[Any]:
    if not report.dimensions:
        return None
    return min(report.dimensions, key=lambda d: d.score)


def select_weakest_dimension(report: SkillReport, config: Dict[str, Any]) -> Optional[Any]:
    """Select the dimension to improve next, respecting priority rules.

    Order of precedence:
    1. Blocker dimensions below ``blocker_threshold`` (in configured order).
    2. High-ROI dimensions below ``improvement_threshold`` (in configured order).
    3. The globally lowest-scoring dimension.
    """
    if not report.dimensions:
        return None

    opt_cfg = config.get("optimization", {})
    priority = opt_cfg.get("priority", {})
    blocker_threshold = priority.get("blocker_threshold", 3)
    improvement_threshold = priority.get("improvement_threshold", 3)
    blockers = priority.get("blockers", [])
    high_roi = priority.get("high_roi", [])

    score_map = {d.code: d.score for d in report.dimensions}

    for code in blockers:
        if code in score_map and score_map[code] < blocker_threshold:
            return next((d for d in report.dimensions if d.code == code), None)

    for code in high_roi:
        if code in score_map and score_map[code] < improvement_threshold:
            return next((d for d in report.dimensions if d.code == code), None)

    return find_weakest_dimension(report)


def build_suggestion(report: SkillReport, config: Dict[str, Any]) -> str:
    # Use the same priority-respecting selection as --auto-edit so the
    # suggestion matches the dimension the editor would actually target.
    weakest = select_weakest_dimension(report, config)
    score, grade = display_score(report, config)
    lines = [
        f"Current score: {score:.1f} / 100 (Grade {grade})",
    ]
    if weakest:
        lines.extend(
            [
                f"Weakest dimension: {weakest.code} {weakest.name} = {weakest.score}/5",
                f"Evidence: {'; '.join(weakest.evidence) if weakest.evidence else 'N/A'}",
                f"Suggestions: {'; '.join(weakest.suggestions) if weakest.suggestions else 'N/A'}",
            ]
        )
    else:
        lines.append("No dimensions found.")

    # Add P0-P3 optimization strategies
    content = _read_skill_md(report.path)
    failure_check = check_failure_mode_encoding(content)
    has_failure_modes = not failure_check.has_issue("D3")

    runtime_warn_count = 0
    if report.runtime_neutrality_report:
        # Simple heuristic: count occurrences of "Warning" or "⚠️"
        runtime_warn_count = report.runtime_neutrality_report.count("⚠️")

    pass_rate = None
    if report.prompts_verification:
        pass_rate = report.prompts_verification.pass_rate

    security_score = None
    for dim in report.dimensions:
        if dim.code == "D9":
            security_score = dim.score

    bloat_ratio = None
    if report.enhancements:
        for issue in report.enhancements.issues:
            if issue.check == "D8" and "size increased to" in issue.message:
                # Extract ratio like "150%"
                import re

                match = re.search(r"(\d+)%", issue.message)
                if match:
                    bloat_ratio = int(match.group(1)) / 100.0

    strategies = get_strategies(
        report.dimensions,
        runtime_warn_count=runtime_warn_count,
        prompts_pass_rate=pass_rate,
        security_score=security_score,
        bloat_ratio=bloat_ratio,
        has_failure_modes=has_failure_modes,
    )
    lines.append("")
    lines.append(format_strategies(strategies))

    lines.append("")
    lines.append(format_cluster_analysis(report.dimensions))

    return "\n".join(lines)


@dataclass
class JudgeResult:
    kept: bool
    applied: bool
    current_score: float
    baseline_score: float
    score_delta: float
    benchmark_ok: bool = False
    benchmark_reason: str = ""
    guard_violations: List[GuardViolation] = field(default_factory=list)
    current_report: SkillReport = field(
        default_factory=lambda: SkillReport(name="", path=Path("."), skill_type="generic")
    )
    current_benchmark: Optional[Dict[str, Any]] = None
    decision_reason: str = ""
    diff: str = ""
    dimension_changes: Dict[str, int] = field(default_factory=dict)


def judge_result_to_dict(result: JudgeResult, config: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a JudgeResult to a JSON-serializable dict."""
    weakest = find_weakest_dimension(result.current_report)
    return {
        "kept": result.kept,
        "applied": result.applied,
        "baseline_score": round(result.baseline_score, 1),
        "current_score": round(result.current_score, 1),
        "score_delta": round(result.score_delta, 1),
        "current_grade": result.current_report.grade(
            result.current_score,
            config.get("scoring", {}).get("grade_thresholds", {}),
        ),
        "benchmark_ok": result.benchmark_ok,
        "benchmark_reason": result.benchmark_reason,
        "decision": "KEEP" if result.kept else "REVERT",
        "decision_reason": result.decision_reason,
        "diff": result.diff,
        "dimension_changes": result.dimension_changes,
        "weakest_dimension": (
            {
                "code": weakest.code,
                "name": weakest.name,
                "score": weakest.score,
            }
            if weakest
            else None
        ),
        "guard_violations": [
            {"rule": v.rule, "severity": v.severity, "message": v.message}
            for v in result.guard_violations
        ],
    }


# --------------------------------------------------------------------------- #
# Diff rendering
# --------------------------------------------------------------------------- #


def render_diff(
    skill_path: Path,
    baseline_md: str,
    current_md: str,
    max_lines: int = 200,
) -> str:
    """Render a diff between baseline and current SKILL.md.

    Uses ``difflib`` against the passed ``baseline_md`` (the
    ``.skillprism_baseline/SKILL.md`` copy). Previously this ran
    ``git add SKILL.md`` then ``git diff --cached`` to compare against HEAD —
    a read-only diff that mutated the git index even in dry-run, and compared
    against the wrong base (HEAD, not the recorded baseline). The difflib path
    is side-effect-free and semantically correct.
    """
    baseline_lines = baseline_md.splitlines(keepends=True)
    current_lines = current_md.splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            baseline_lines,
            current_lines,
            fromfile="SKILL.md (baseline)",
            tofile="SKILL.md (current)",
        )
    )

    lines = diff.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines.append(f"... ({len(lines)} lines shown; use --diff-lines to see more)")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Judge candidate edit
# --------------------------------------------------------------------------- #


def judge_candidate(
    skill_path: Path,
    config: Dict[str, Any],
    baseline: Dict[str, Any],
    benchmark_registry: Optional[Path] = None,
    benchmark_output_dir: Optional[Path] = None,
    code_path: Optional[Path] = None,
    min_gain: float = 1.0,
    allow_regression: float = 0.5,
    apply: bool = False,
    ratchet: bool = False,
    verbose: bool = False,
    context: Optional[Dict[str, Any]] = None,
    llm_judge: Optional[LLMJudge] = None,
    llm_judgments: Optional[Dict[str, MultiJudgeResult]] = None,
    show_diff: bool = True,
    diff_lines: int = 200,
    edit_code: bool = False,
) -> JudgeResult:
    """Judge the current SKILL.md against the stored baseline.

    Public entry point: acquires an advisory lock (``.skillprism.lock``) so
    concurrent optimizers (CI + local dev) cannot race the baseline
    read-modify-write or clobber each other's keep/revert. Internal callers
    that already hold the lock use ``_judge_candidate_unlocked`` directly to
    avoid re-entrant flock deadlock.
    """
    with file_lock(skill_path / ".skillprism.lock"):
        return _judge_candidate_unlocked(
            skill_path,
            config,
            baseline,
            benchmark_registry=benchmark_registry,
            benchmark_output_dir=benchmark_output_dir,
            code_path=code_path,
            min_gain=min_gain,
            allow_regression=allow_regression,
            apply=apply,
            ratchet=ratchet,
            verbose=verbose,
            context=context,
            llm_judge=llm_judge,
            show_diff=show_diff,
            diff_lines=diff_lines,
            edit_code=edit_code,
        )


def _run_bloat_gate(
    skill_path: Path,
    baseline_md: str,
    baseline_score: float,
    current_score: float,
    score_delta: float,
    current_report: SkillReport,
    apply: bool,
) -> Optional[JudgeResult]:
    """Reject edits that bloat SKILL.md beyond 150% of baseline.

    Returns a REVERT ``JudgeResult`` if the bloat guard fires on an
    error-severity finding, else ``None`` (caller continues). Honors
    ``apply``: dry-run reports the decision without touching the file.
    """
    current_md_text = _read_skill_md(skill_path)
    # Pass the baseline SKILL.md copy explicitly — check_bloat's default lookup
    # targets a .bak file that save_baseline never writes, so without this the
    # guard would silently never fire.
    baseline_md_path = skill_path / BASELINE_DIR / "SKILL.md"
    bloat_check = check_bloat(
        skill_path, current_md_text, baseline_md_path if baseline_md_path.exists() else None
    )
    if not bloat_check.issues:
        return None
    for issue in bloat_check.issues:
        if issue.severity != "error":
            continue
        print(f"Bloat guard triggered: {issue.message}")
        bloat_reason = f"bloat: {issue.message}"
        if apply:
            print("Reverting edit; reduce SKILL.md size and try again.")
            save_skill_md(skill_path, baseline_md)
            status = "revert"
        else:
            print("Pass --apply to revert the bloated edit.")
            status = "human-decide"
        record_attempt(
            skill_path,
            old_score=baseline_score,
            new_score=current_score,
            status=status,
            dimension="D8",
            note=f"bloat guard: {issue.message}",
            eval_mode="static",
        )
        return JudgeResult(
            kept=False,
            applied=apply,
            current_score=current_score,
            baseline_score=baseline_score,
            score_delta=score_delta,
            benchmark_ok=False,
            benchmark_reason="bloat guard",
            guard_violations=[
                GuardViolation(rule="bloat", severity="block", message=issue.message)
            ],
            current_report=current_report,
            decision_reason=bloat_reason,
            diff="",
            dimension_changes={},
        )
    return None


def _judge_candidate_unlocked(
    skill_path: Path,
    config: Dict[str, Any],
    baseline: Dict[str, Any],
    benchmark_registry: Optional[Path] = None,
    benchmark_output_dir: Optional[Path] = None,
    code_path: Optional[Path] = None,
    min_gain: float = 1.0,
    allow_regression: float = 0.5,
    apply: bool = False,
    ratchet: bool = False,
    verbose: bool = False,
    context: Optional[Dict[str, Any]] = None,
    llm_judge: Optional[LLMJudge] = None,
    llm_judgments: Optional[Dict[str, MultiJudgeResult]] = None,
    show_diff: bool = True,
    diff_lines: int = 200,
    edit_code: bool = False,
) -> JudgeResult:
    """Judge the current SKILL.md against the stored baseline (no lock).

    By default this is a dry-run: it reports the decision but does NOT keep or
    revert the edit. Pass ``apply=True`` to actually apply the decision.
    """
    use_git = git_available(skill_path)
    baseline_md = load_baseline_skill_md(skill_path)

    current_report = evaluate_skill(
        skill_path, config, verbose=verbose, llm_judge=llm_judge, llm_judgments=llm_judgments
    )
    current_score, current_grade = display_score(current_report, config)
    baseline_score = baseline.get("score", 0.0)
    score_delta = current_score - baseline_score

    bloat_result = _run_bloat_gate(
        skill_path,
        baseline_md,
        baseline_score,
        current_score,
        score_delta,
        current_report,
        apply,
    )
    if bloat_result is not None:
        return bloat_result

    # Compute per-dimension changes for structured judgment.
    baseline_dim_scores = baseline.get("dimension_scores", {})
    dimension_changes: Dict[str, int] = {}
    for dim in current_report.dimensions:
        baseline_dim = baseline_dim_scores.get(dim.code)
        if baseline_dim is not None:
            dimension_changes[dim.code] = dim.score - int(baseline_dim)
    if dimension_changes:
        print("\nDimension changes (current - baseline):")
        for code, delta in sorted(dimension_changes.items()):
            print(f"  {code}: {delta:+d}")

    current_md = load_skill_md(skill_path)
    diff = ""
    if show_diff:
        diff = render_diff(skill_path, baseline_md, current_md, max_lines=diff_lines)
        if diff:
            print("\nSKILL.md diff (baseline → current):")
            print(diff)
        else:
            print("\nNo SKILL.md diff detected.")

    print(f"\nCurrent: {current_score:.1f} / 100 (Grade {current_grade})")
    print(f"Baseline: {baseline_score:.1f} / 100")
    print(f"Delta: {score_delta:+.1f}")

    # Optional benchmark gate
    current_benchmark: Optional[Dict[str, Any]] = None
    benchmark_ok = True
    benchmark_reason = "benchmark not enabled"
    skill_type = detect_skill_type(skill_path, config)
    if benchmark_registry and benchmark_registry.exists() and skill_type:
        current_benchmark = run_skill_benchmark(
            skill_path,
            skill_type,
            benchmark_registry,
            benchmark_output_dir or Path("benchmarks/latest"),
            code_path,
        )
        if current_benchmark:
            print(_format_benchmark_summary(current_benchmark))
        benchmark_ok, benchmark_reason = benchmark_acceptable(
            baseline.get("benchmark"), current_benchmark
        )
        print(f"Benchmark gate: {benchmark_reason}")

    # Anti-pattern guards
    guard_ctx = dict(context or {})
    guard_ctx.setdefault("baseline_dict", baseline)
    baseline_report = baseline.get("report")
    if baseline_report is None:
        # Reconstruct a minimal SkillReport from baseline dimension scores
        baseline_report = SkillReport(
            name=skill_path.name,
            path=skill_path,
            skill_type=skill_type or "generic",
            dimensions=[
                DimensionResult(code=code, name=code, score=score)
                for code, score in baseline.get("dimension_scores", {}).items()
            ],
        )
    violations = run_guards(skill_path, baseline_report, current_report, guard_ctx)

    # Extra smoke-test gate when code assets are edited
    if edit_code:
        skill_type = detect_skill_type(skill_path, config)
        if skill_type:
            smoke_report = run_smoke_tests(
                skill_path, skill_type, config, verbose=verbose, allow_exec=edit_code
            )
            if not smoke_report.all_pass:
                failed = [t.name for t in smoke_report.tests if not t.passed]
                violations.append(
                    GuardViolation(
                        rule="smoke_test",
                        severity="block",
                        message=f"Smoke test failed for edited code assets: {', '.join(failed)}",
                    )
                )

    if violations:
        print("\n" + format_violations(violations))

    blockers = [v for v in violations if v.severity == "block"]

    bench_improved = benchmark_improved(baseline.get("benchmark"), current_benchmark)

    would_keep = True
    reason = ""

    # Security dimension (D9) regression is an automatic veto.
    d9_delta = dimension_changes.get("D9", 0)
    if d9_delta < 0:
        would_keep = False
        reason = f"Security dimension (D9) regressed by {-d9_delta} point(s)"
    elif blockers:
        would_keep = False
        reason = f"guard blocked: {blockers[0].message}"
    elif not benchmark_ok:
        would_keep = False
        reason = benchmark_reason
    elif score_delta >= min_gain:
        would_keep = True
        reason = "Rubric score improved"
    elif bench_improved and score_delta >= -allow_regression:
        would_keep = True
        reason = "Benchmark improved while Rubric did not regress"
    else:
        would_keep = False
        reason = f"No improvement (delta {score_delta:+.1f} < min_gain {min_gain})"

    # Ratchet: never go below historical best
    if ratchet and would_keep:
        historical_best = baseline.get("historical_best_score", baseline_score)
        if current_score < historical_best - 0.01:
            would_keep = False
            reason = f"Ratchet: current {current_score:.1f} < historical best {historical_best:.1f}"

    print(f"Decision: {'KEEP' if would_keep else 'REVERT'} ({reason})")

    # Identify weakest changed dimension for history
    weakest_dim = "all"
    if dimension_changes:
        weakest_dim = min(dimension_changes.items(), key=lambda x: x[1])[0]

    status = "keep" if would_keep else "revert"
    if not apply:
        status = "human-decide"
    try:
        record_attempt(
            skill_path,
            old_score=baseline_score,
            new_score=current_score,
            status=status,
            dimension=weakest_dim,
            note=reason,
            eval_mode="static",
            metadata={
                "benchmark_ok": benchmark_ok,
                "guard_violations": [v.message for v in violations],
                "dimension_changes": dimension_changes,
            },
        )
    except Exception as exc:
        # History is the primary audit trail; surface write failures instead
        # of silently dropping them (disk errors, JSON-serialization bugs).
        print(f"Warning: failed to record optimization attempt to history: {exc}")

    if not apply:
        print("(dry-run: pass --apply to actually keep or revert)")
        return JudgeResult(
            kept=would_keep,
            applied=False,
            current_score=current_score,
            baseline_score=baseline_score,
            score_delta=score_delta,
            benchmark_ok=benchmark_ok,
            benchmark_reason=benchmark_reason,
            guard_violations=violations,
            current_report=current_report,
            current_benchmark=current_benchmark,
            decision_reason=reason,
            diff=diff,
            dimension_changes=dimension_changes,
        )

    if would_keep:
        # Single-dimension constraint check
        changed_dims = [c for c, d in dimension_changes.items() if abs(d) >= 2]
        if len(changed_dims) > 1:
            print(
                f"Warning: multiple dimensions changed significantly {changed_dims}; "
                "consider a narrower edit next round."
            )
        save_baseline(skill_path, current_report, current_benchmark)
        if use_git:
            try:
                git_commit(
                    skill_path,
                    f"[skill-optimizer] keep improved SKILL.md (score {current_score:.1f})",
                )
            except subprocess.CalledProcessError:
                print("Warning: git commit failed; baseline updated but no commit was made.")
        print("Edit kept and baseline updated.")
    else:
        # apply=True, decision=REVERT: discard the uncommitted candidate edit.
        # git_revert restores SKILL.md to HEAD (discards staged+unstaged changes);
        # if git is unavailable or checkout fails, fall back to the baseline copy.
        if use_git:
            try:
                git_revert(skill_path)
            except subprocess.CalledProcessError:
                print("Warning: git checkout failed; falling back to baseline copy.")
                save_skill_md(skill_path, baseline_md)
        else:
            save_skill_md(skill_path, baseline_md)
        if edit_code:
            if restore_code_assets(skill_path):
                print("Code assets restored from snapshot.")
            else:
                print("Warning: no code asset snapshot found; skipping code restore.")
        print("Edit reverted.")

    return JudgeResult(
        kept=would_keep,
        applied=True,
        current_score=current_score,
        baseline_score=baseline_score,
        score_delta=score_delta,
        benchmark_ok=benchmark_ok,
        benchmark_reason=benchmark_reason,
        guard_violations=violations,
        current_report=current_report,
        current_benchmark=current_benchmark,
        decision_reason=reason,
        diff=diff,
        dimension_changes=dimension_changes,
    )


def explore_rewrite(
    skill_path: Path,
    config: Dict[str, Any],
    editor: SkillEditor,
    benchmark_registry: Optional[Path] = None,
    benchmark_output_dir: Optional[Path] = None,
    code: Optional[Path] = None,
    min_gain: float = 1.0,
    allow_regression: float = 0.5,
    ratchet: bool = False,
    context: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
    llm_judge: Optional[LLMJudge] = None,
    llm_judgments: Optional[Dict[str, MultiJudgeResult]] = None,
    apply: bool = False,
) -> JudgeResult:
    """Locked entry point for an exploratory rewrite of SKILL.md.

    Serializes concurrent optimizers on the same skill directory before
    delegating to the unlocked implementation.
    """
    with file_lock(skill_path / ".skillprism.lock"):
        return _explore_rewrite_unlocked(
            skill_path,
            config,
            editor,
            benchmark_registry=benchmark_registry,
            benchmark_output_dir=benchmark_output_dir,
            code=code,
            min_gain=min_gain,
            allow_regression=allow_regression,
            ratchet=ratchet,
            context=context,
            verbose=verbose,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
            apply=apply,
        )


def _explore_rewrite_unlocked(
    skill_path: Path,
    config: Dict[str, Any],
    editor: SkillEditor,
    benchmark_registry: Optional[Path] = None,
    benchmark_output_dir: Optional[Path] = None,
    code: Optional[Path] = None,
    min_gain: float = 1.0,
    allow_regression: float = 0.5,
    ratchet: bool = False,
    context: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
    llm_judge: Optional[LLMJudge] = None,
    llm_judgments: Optional[Dict[str, MultiJudgeResult]] = None,
    apply: bool = False,
) -> JudgeResult:
    """Perform an exploratory rewrite of SKILL.md to escape local optima.

    Inspired by darwin-skill Phase 2.5: stash the current best, rewrite from
    scratch, and keep only if the rewrite scores higher.
    """
    if not editor.is_available():
        print("Error: no skill editor configured for exploratory rewrite.")
        return JudgeResult(
            kept=False,
            applied=False,
            current_score=0.0,
            baseline_score=0.0,
            score_delta=0.0,
            decision_reason="no editor configured",
        )

    baseline = load_baseline(skill_path)
    if not baseline:
        print("Error: no baseline found; record a baseline before exploratory rewrite.")
        return JudgeResult(
            kept=False,
            applied=False,
            current_score=0.0,
            baseline_score=0.0,
            score_delta=0.0,
            decision_reason="no baseline",
        )

    baseline_score = baseline.get("score", 0.0)

    # Save current best to a stash file
    stash_path = skill_path / BASELINE_DIR / "SKILL.md.stash"
    current_md = _read_skill_md(skill_path)
    stash_path.write_text(current_md, encoding="utf-8")
    print(f"Stashed current best to {stash_path}")

    try:
        # Build a rewrite prompt focused on overall restructuring
        current_report = evaluate_skill(
            skill_path, config, verbose=verbose, llm_judge=llm_judge, llm_judgments=llm_judgments
        )
        weakest = select_weakest_dimension(current_report, config)
        weakest_dict = None
        if weakest:
            weakest_dict = {
                "code": weakest.code,
                "name": weakest.name,
                "score": weakest.score,
                "suggestions": weakest.suggestions,
            }

        prompt = build_editor_prompt(
            skill_path,
            current_md,
            weakest_dict,
            baseline_score,
            strategy="exploratory_rewrite",
            edit_code=False,
            single_dimension=False,
        )
        print("Invoking exploratory rewrite editor...")
        new_md = editor.edit(prompt)
        if new_md is None:
            print("Error: exploratory rewrite editor returned no content.")
            return JudgeResult(
                kept=False,
                applied=False,
                current_score=0.0,
                baseline_score=baseline_score,
                score_delta=0.0,
                decision_reason="editor returned no content",
            )
        save_skill_md(skill_path, new_md.content)

        # Judge the rewrite (unlocked: explore_rewrite is a single short path;
        # the standalone --judge CLI path acquires the lock via judge_candidate).
        result = _judge_candidate_unlocked(
            skill_path,
            config,
            baseline,
            benchmark_registry=benchmark_registry,
            benchmark_output_dir=benchmark_output_dir,
            code_path=code,
            min_gain=min_gain,
            allow_regression=allow_regression,
            ratchet=ratchet,
            context=context,
            verbose=verbose,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
            apply=apply,
            edit_code=False,
        )
        return result

    except Exception as e:
        print(f"Exploratory rewrite failed: {e}")
        # Restore stashed version
        if stash_path.exists():
            save_skill_md(skill_path, stash_path.read_text(encoding="utf-8"))
            print("Restored stashed version.")
        return JudgeResult(
            kept=False,
            applied=False,
            current_score=0.0,
            baseline_score=baseline_score,
            score_delta=0.0,
            decision_reason=f"exploratory rewrite failed: {e}",
        )


def _run_auto_edit_rounds(
    skill_path: Path,
    config: Dict[str, Any],
    editor: SkillEditor,
    benchmark_registry: Optional[Path],
    benchmark_output_dir: Optional[Path],
    code: Optional[Path],
    min_gain: float,
    allow_regression: float,
    ratchet: bool,
    context: Optional[Dict[str, Any]],
    verbose: bool,
    llm_judge: Optional[LLMJudge],
    llm_judgments: Optional[Dict[str, MultiJudgeResult]] = None,
    max_rounds: int = 1,
    stop_on_regression: bool = True,
    edit_code: bool = False,
) -> int:
    """Locked entry: serialize concurrent auto-edit runs on the same skill."""
    with file_lock(skill_path / ".skillprism.lock"):
        return _run_auto_edit_rounds_unlocked(
            skill_path,
            config,
            editor,
            benchmark_registry,
            benchmark_output_dir,
            code,
            min_gain,
            allow_regression,
            ratchet,
            context,
            verbose,
            llm_judge,
            llm_judgments,
            max_rounds=max_rounds,
            stop_on_regression=stop_on_regression,
            edit_code=edit_code,
        )


def _run_auto_edit_rounds_unlocked(
    skill_path: Path,
    config: Dict[str, Any],
    editor: SkillEditor,
    benchmark_registry: Optional[Path],
    benchmark_output_dir: Optional[Path],
    code: Optional[Path],
    min_gain: float,
    allow_regression: float,
    ratchet: bool,
    context: Optional[Dict[str, Any]],
    verbose: bool,
    llm_judge: Optional[LLMJudge],
    llm_judgments: Optional[Dict[str, MultiJudgeResult]] = None,
    max_rounds: int = 1,
    stop_on_regression: bool = True,
    edit_code: bool = False,
) -> int:
    """Run autonomous optimize-edit-judge-apply rounds using a configured editor.

    The editor command (e.g. an LLM wrapper) is responsible for rewriting SKILL.md.
    skillPrism remains the independent measurement gate that decides keep/revert.
    After each kept edit, the improved version becomes the new baseline for the
    next round, allowing simple hill-climbing.
    """
    if not editor.is_available():
        print(
            "Error: no skill editor is configured. Set SKILLPRISM_EDITOR_COMMAND or "
            "configure `editor.command` in skill_rubric_types.yaml."
        )
        return 2

    # Ensure a baseline exists
    baseline = load_baseline(skill_path)
    if not baseline:
        print("No baseline found; recording baseline before editing.")
        report = evaluate_skill(
            skill_path, config, verbose=verbose, llm_judge=llm_judge, llm_judgments=llm_judgments
        )
        skill_type = detect_skill_type(skill_path, config)
        benchmark = None
        if benchmark_registry and skill_type:
            benchmark = run_skill_benchmark(
                skill_path,
                skill_type,
                benchmark_registry,
                benchmark_output_dir,
                code,
            )
        save_baseline(skill_path, report, benchmark)
        baseline = load_baseline(skill_path)

    if baseline is None:
        print("Error: failed to record baseline.")
        return 2

    if edit_code:
        snapshot_code_assets(skill_path)
        print("Code asset snapshot recorded for --edit-code rollback.")

    max_rounds = max(1, max_rounds)
    final_exit = 1
    for round_idx in range(1, max_rounds + 1):
        print(f"\n=== Auto-edit round {round_idx}/{max_rounds} ===")

        # Evaluate current state and identify weakest dimension
        current_report = evaluate_skill(
            skill_path, config, verbose=verbose, llm_judge=llm_judge, llm_judgments=llm_judgments
        )
        current_score, _ = display_score(current_report, config)
        weakest = select_weakest_dimension(current_report, config)
        weakest_dict: Optional[Dict[str, Any]] = None
        related: List[str] = []
        if weakest:
            dimension_scores = {d.code: d.score for d in current_report.dimensions}
            related = find_related_dimensions(
                weakest.code,
                dimension_scores,
                config,
                threshold=config.get("optimization", {})
                .get("priority", {})
                .get("improvement_threshold", 3),
            )
            weakest_dict = {
                "code": weakest.code,
                "name": weakest.name,
                "score": weakest.score,
                "suggestions": weakest.suggestions,
            }
        weakest_code = weakest_dict["code"] if weakest_dict else "overall"

        current_md = (skill_path / "SKILL.md").read_text(encoding="utf-8")
        strategy = get_strategy(
            weakest_dict["code"] if weakest_dict else None,
            related=related if related else None,
        )
        prompt = build_editor_prompt(
            skill_path,
            current_md,
            weakest_dict,
            current_score,
            strategy,
            edit_code=edit_code,
            single_dimension=True,
        )

        print(f"Invoking skill editor to improve dimension {weakest_code}...")
        result = editor.edit(prompt)
        if result is None:
            print("Error: skill editor failed or returned invalid content.")
            return 2

        (skill_path / "SKILL.md").write_text(result.content, encoding="utf-8")

        # Judge and apply keep/revert against the current baseline.
        # Unlocked variant: _run_auto_edit_rounds already holds .skillprism.lock.
        judge_result = _judge_candidate_unlocked(
            skill_path,
            config,
            cast(Dict[str, Any], baseline),
            benchmark_registry=benchmark_registry,
            benchmark_output_dir=benchmark_output_dir,
            code_path=code,
            min_gain=min_gain,
            allow_regression=allow_regression,
            ratchet=ratchet,
            context=context,
            apply=True,
            verbose=verbose,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
        )

        if judge_result.kept:
            final_exit = 0
            # Reload baseline so the next round climbs from the improved version
            baseline = load_baseline(skill_path)
            if round_idx < max_rounds:
                print("Edit kept. Starting next round from improved version.")
            if round_idx == max_rounds:
                print("Edit kept. Max rounds reached.")
        else:
            print("Edit reverted. Stopping auto-edit loop.")
            if stop_on_regression:
                print("--stop-on-regression enabled: no further rounds will run.")
            return 1

    return final_exit


# --------------------------------------------------------------------------- #
# Main CLI
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Improve a skill by editing SKILL.md/code and judging the change."
    )
    parser.add_argument("skill", help="Path to a skill directory")
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG), help="Path to skill type config YAML"
    )
    parser.add_argument(
        "--record-baseline", action="store_true", help="Record current SKILL.md as baseline"
    )
    parser.add_argument(
        "--suggest", action="store_true", help="Print the weakest dimension and suggestions"
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Judge current SKILL.md against baseline; keep or revert",
    )
    parser.add_argument(
        "--output-json",
        help="Write judge result as JSON to the given path",
    )
    parser.add_argument(
        "--benchmark-registry", help="Benchmark registry YAML (enables benchmark gate)"
    )
    parser.add_argument(
        "--benchmark-output-dir",
        default="benchmarks/latest",
        help="Directory for benchmark outputs",
    )
    parser.add_argument("--code", help="Path to skill code to use during benchmarking")
    parser.add_argument(
        "--min-gain", type=float, default=1.0, help="Minimum score gain to keep an edit"
    )
    parser.add_argument(
        "--allow-regression",
        type=float,
        default=0.5,
        help="Max Rubric score drop allowed when benchmark improves",
    )
    parser.add_argument("--clear-baseline", action="store_true", help="Remove stored baseline")
    parser.add_argument(
        "--apply", action="store_true", help="Actually keep or revert the edit (default is dry-run)"
    )
    parser.add_argument(
        "--ratchet", action="store_true", help="Never accept a score below the historical best"
    )
    parser.add_argument(
        "--auto-edit",
        action="store_true",
        help="Autonomously edit SKILL.md using a configured editor command",
    )
    parser.add_argument(
        "--editor-command", help="Command to call the SKILL.md editor (overrides env/config)"
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=1,
        help="Maximum auto-edit rounds when using --auto-edit (default: 1)",
    )
    parser.add_argument(
        "--no-stop-on-regression",
        action="store_true",
        help="Continue auto-edit rounds after a reverted edit (default: stop on regression)",
    )
    parser.add_argument(
        "--editor-model", help="Model name used to edit SKILL.md (for self-judge guard)"
    )
    parser.add_argument("--judge-model", help="Model name used to judge (for self-judge guard)")
    parser.add_argument(
        "--show-diff",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Render SKILL.md diff in judge output (default: --show-diff)",
    )
    parser.add_argument(
        "--diff-lines",
        type=int,
        default=200,
        help="Maximum number of diff lines to display (default: 200)",
    )
    parser.add_argument(
        "--edit-code",
        action="store_true",
        help="Allow --auto-edit to modify code assets (scripts, examples, requirements, etc.)",
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
        "--llm-judgments",
        help="Path to pre-computed .skillprism_llm_judgments.json (Agent-generated)",
    )
    parser.add_argument("--auto", action="store_true", help="Deprecated; use --apply instead")
    parser.add_argument(
        "--history", action="store_true", help="Show optimization history for the skill"
    )
    parser.add_argument(
        "--explore-rewrite",
        action="store_true",
        help="Perform an exploratory rewrite of SKILL.md to escape local optima",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Print evaluation progress")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)

    # Optional LLM-as-judge
    llm_judge: Optional[LLMJudge] = None
    if args.llm_judge:
        llm_judge = LLMJudge.from_config(config) or LLMJudge.from_env()
        if args.llm_judge_command:
            llm_judge = LLMJudge(
                command=args.llm_judge_command.split(),
                weight=args.llm_judge_weight,
            )
        elif llm_judge is not None:
            llm_judge.weight = args.llm_judge_weight
        if llm_judge is None or not llm_judge.is_available():
            print("Warning: --llm-judge requested but no LLM judge command configured.")
            print("Set SKILLPRISM_LLM_JUDGE_COMMAND or add llm_judge.command to the config.")
            llm_judge = None

    # Load pre-computed LLM judgments if provided (Agent-generated).
    llm_judgments: Optional[Dict[str, MultiJudgeResult]] = None
    if args.llm_judgments:
        try:
            data = json.loads(Path(args.llm_judgments).read_text(encoding="utf-8"))
            llm_judgments = {j["dimension"]: MultiJudgeResult(**j) for j in data.get("judges", [])}
        except Exception as e:
            print(f"Warning: failed to load LLM judgments: {e}")

    skill_path = Path(args.skill)
    if not skill_path.is_absolute():
        skill_path = Path.cwd() / skill_path

    if not skill_path.is_dir():
        print(f"Error: {skill_path} is not a directory")
        return 2

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"Error: {skill_md} not found")
        record_attempt(
            skill_path,
            old_score=0.0,
            new_score=0.0,
            status="error",
            dimension="all",
            note="SKILL.md not found",
            eval_mode="static",
        )
        return 2

    if args.clear_baseline:
        clear_baseline(skill_path)
        print("Baseline cleared.")
        return 0

    if args.history:
        records = load_history(skill_path)
        print(format_history_table(records))
        return 0

    if args.explore_rewrite:
        apply = args.apply or args.auto
        editor = SkillEditor.from_config(config) or SkillEditor.from_env()
        if editor is None or not editor.is_available():
            print(
                "Error: --explore-rewrite requested but no editor command is configured.\n"
                "Set SKILLPRISM_EDITOR_COMMAND or add editor.command to skill_rubric_types.yaml."
            )
            return 2
        ensure_git_ready(skill_path)
        result = explore_rewrite(
            skill_path,
            config,
            editor,
            benchmark_registry=Path(args.benchmark_registry) if args.benchmark_registry else None,
            benchmark_output_dir=Path(args.benchmark_output_dir),
            code=Path(args.code) if args.code else None,
            min_gain=args.min_gain,
            allow_regression=args.allow_regression,
            ratchet=args.ratchet,
            context={"editor_model": args.editor_model, "judge_model": args.judge_model},
            verbose=args.verbose,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
            apply=apply,
        )
        print(
            f"Exploratory rewrite: {'KEPT' if result.kept else 'REVERTED'} ({result.decision_reason})"
        )
        return 0 if result.kept else 1

    if args.record_baseline:
        report = evaluate_skill(
            skill_path,
            config,
            verbose=args.verbose,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
        )
        skill_type = detect_skill_type(skill_path, config)
        benchmark = None
        if args.benchmark_registry and skill_type:
            benchmark = run_skill_benchmark(
                skill_path,
                skill_type,
                Path(args.benchmark_registry),
                Path(args.benchmark_output_dir),
                Path(args.code) if args.code else None,
            )
        save_baseline(skill_path, report, benchmark)
        score, grade = display_score(report, config)
        print(f"Baseline recorded: {score:.1f} / 100 (Grade {grade})")
        if benchmark:
            print(_format_benchmark_summary(benchmark))
        return 0

    if args.suggest:
        report = evaluate_skill(
            skill_path,
            config,
            verbose=args.verbose,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
        )
        print(build_suggestion(report, config))
        return 0

    apply = args.apply or args.auto

    if args.judge:
        baseline = load_baseline(skill_path)
        if not baseline:
            print(
                f"Error: no baseline found. Run `python -m skillprism.optimize_skill {skill_path} --record-baseline` first."
            )
            return 2
        context = {
            "editor_model": args.editor_model,
            "judge_model": args.judge_model,
        }
        result = judge_candidate(
            skill_path,
            config,
            baseline,
            benchmark_registry=Path(args.benchmark_registry) if args.benchmark_registry else None,
            benchmark_output_dir=Path(args.benchmark_output_dir),
            code_path=Path(args.code) if args.code else None,
            min_gain=args.min_gain,
            allow_regression=args.allow_regression,
            apply=apply,
            ratchet=args.ratchet,
            verbose=args.verbose,
            context=context,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
            show_diff=args.show_diff,
            diff_lines=args.diff_lines,
            edit_code=args.edit_code,
        )
        if args.output_json:
            output_json_path = Path(args.output_json)
            output_json_path.parent.mkdir(parents=True, exist_ok=True)
            output_json_path.write_text(
                json.dumps(judge_result_to_dict(result, config), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Judge result written to {output_json_path}")
        if not apply:
            print(
                "\nDry-run complete. Review the decision above, then re-run with --apply to enforce it."
            )
        return 0 if result.kept else 1

    # Autonomous edit round using a configured SKILL.md editor
    if args.auto_edit and not (args.record_baseline or args.clear_baseline):
        if not apply:
            print(
                "--auto-edit will rewrite SKILL.md. "
                "Use --apply to run the full edit + judge + keep/revert cycle."
            )
            return 1
        auto_editor: Optional[SkillEditor] = (
            SkillEditor.from_config(config) or SkillEditor.from_env()
        )
        if args.editor_command:
            auto_editor = SkillEditor(command=args.editor_command)
        if auto_editor is None or not auto_editor.is_available():
            print(
                "Error: --auto-edit requested but no editor command is configured.\n"
                "Set SKILLPRISM_EDITOR_COMMAND or add editor.command to skill_rubric_types.yaml."
            )
            return 2
        context = {
            "editor_model": args.editor_model,
            "judge_model": args.judge_model,
        }
        return _run_auto_edit_rounds(
            skill_path,
            config,
            auto_editor,
            benchmark_registry=Path(args.benchmark_registry) if args.benchmark_registry else None,
            benchmark_output_dir=Path(args.benchmark_output_dir),
            code=Path(args.code) if args.code else None,
            min_gain=args.min_gain,
            allow_regression=args.allow_regression,
            ratchet=args.ratchet,
            context=context,
            verbose=args.verbose,
            llm_judge=llm_judge,
            llm_judgments=llm_judgments,
            max_rounds=args.max_rounds,
            stop_on_regression=not args.no_stop_on_regression,
            edit_code=args.edit_code,
        )

    # Default: print usage hint
    print("Use one of: --record-baseline, --suggest, --judge, --auto-edit, --clear-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
