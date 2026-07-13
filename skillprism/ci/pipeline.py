#!/usr/bin/env python3
"""CI pipeline for skill quality gating.

The CI pipeline is intentionally limited to deterministic, objective checks:

1. Rubric static evaluation
2. Smoke tests
3. Dependency reproducibility checks
4. Security scanning

Dynamic benchmarks are optional and require a pre-generated code artifact
(``--code``). The CI pipeline does NOT call LLMs to generate code.

For the natural-language-driven full loop (including LLM code generation and
SKILL.md optimization), use the Agent-facing skills instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import yaml

from skillprism.benchmark.regression import compare_suite, load_yaml
from skillprism.benchmark.runner import run_benchmarks
from skillprism.dependency_checker import check_dependencies
from skillprism.evaluate_skill_rubric import (
    DEFAULT_CONFIG,
    evaluate_skill,
    get_grade_thresholds,
    get_weights,
    load_config,
)
from skillprism.security_evaluator import evaluate_d9_security
from skillprism.test_prompts import artifacts_dir


class CIPipeline:
    """Run deterministic skill quality checks suitable for CI."""

    def __init__(
        self,
        skill: str,
        registry_path: Path,
        baseline_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        self.skill = skill
        self.registry_path = registry_path
        self.baseline_path = baseline_path
        self.output_dir = output_dir or artifacts_dir(Path(skill)) / "ci"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = config_path or DEFAULT_CONFIG
        self.config = load_config(self.config_path)

    def run(
        self,
        level: Optional[int] = None,
        suite: Optional[str] = None,
        ratchet: bool = False,
        stop_on_regression: bool = True,
        output_format: str = "yaml",
        static_only: bool = False,
        run_benchmark: bool = True,
        run_smoke: bool = True,
        run_deps: bool = True,
        run_deps_dry_run: bool = False,
        code_path: Optional[Path] = None,
        results_mode: bool = True,
        agent_command: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute the pipeline.

        By default this runs the dynamic benchmark suite for backward
        compatibility. For CI static-only gating, set ``static_only=True`` or
        ``run_benchmark=False``. Dynamic benchmarks require a pre-generated
        code artifact (``--code``); the pipeline does not generate code.
        """
        skill_path = Path(self.skill)
        if not skill_path.is_dir():
            # Assume skill name relative to ./skills/<name>
            skill_path = Path(".") / "skills" / self.skill
        skill_path = skill_path.resolve()

        results: Dict[str, Any] = {"skill": self.skill, "static": {}}
        static_available = skill_path.is_dir()

        if static_only and not static_available:
            return {
                "skill": self.skill,
                "_all_pass": False,
                "error": f"Skill directory not found: {skill_path}",
            }

        static_all_pass = True
        if static_available:
            # 1. Rubric static evaluation
            rubric_report = evaluate_skill(
                skill_path,
                self.config,
                skill_type=None,
                verbose=False,
                run_smoke=run_smoke,
                run_deps=run_deps and run_deps_dry_run,
            )
            results["static"]["rubric"] = {
                "skill_type": rubric_report.skill_type,
                "score": rubric_report.total_weighted(get_weights(self.config)),
                "grade": rubric_report.grade(
                    rubric_report.total_weighted(get_weights(self.config)),
                    get_grade_thresholds(self.config),
                ),
                "dimensions": {d.code: d.score for d in rubric_report.dimensions},
                "errors": rubric_report.errors,
                "smoke_report": rubric_report.smoke_report,
                "dependency_report": rubric_report.dependency_report,
                "skill_lens_report": rubric_report.skill_lens_report,
                "runtime_neutrality_report": rubric_report.runtime_neutrality_report,
                "test_prompts_report": rubric_report.test_prompts_report,
            }

            # 2. Security scan (deterministic)
            sec_score, sec_evidence, sec_suggestions, sec_findings = evaluate_d9_security(
                skill_path, rubric_report.skill_type, self.config
            )
            results["static"]["security"] = {
                "score": sec_score,
                "evidence": sec_evidence,
                "suggestions": sec_suggestions,
                "findings": [
                    {
                        "id": f.id,
                        "name": f.name,
                        "severity": f.severity,
                        "location": f.location,
                        "description": f.description,
                        "matched": f.matched,
                    }
                    for f in sec_findings
                ],
            }

            # 3. Dependency check (lightweight, no dry-run unless requested)
            dep_report = check_dependencies(
                skill_path, rubric_report.skill_type, self.config, run_dry_run=run_deps_dry_run
            )
            results["static"]["dependencies"] = {
                "all_pass": dep_report.all_pass,
                "checks": [
                    {"name": c.name, "passed": c.passed, "evidence": c.evidence, "error": c.error}
                    for c in dep_report.checks
                ],
            }

            # Determine static pass/fail
            static_all_pass = (
                not rubric_report.errors
                and results["static"]["security"]["score"] >= 3
                and results["static"]["dependencies"]["all_pass"]
            )
            results["static"]["_all_pass"] = static_all_pass

        if static_only:
            results["_all_pass"] = static_all_pass
            return results

        # 4. Optional dynamic benchmark (requires committed/generated code artifact)
        if not run_benchmark:
            results["_all_pass"] = static_all_pass
            return results

        # A concrete code artifact means we should execute it, not just verify.
        if code_path is not None:
            results_mode = False

        results_path = self.output_dir / f"results.{output_format}"
        benchmark_results = run_benchmarks(
            self.skill,
            self.registry_path,
            code_path=code_path,
            output_path=results_path,
            suite=suite,
            level=level,
            output_format=output_format,
            results_mode=results_mode,
            agent_command=agent_command,
        )

        regression: Optional[Dict[str, Any]] = None
        if self.baseline_path and self.baseline_path.exists():
            baseline = load_yaml(self.baseline_path)
            regression = compare_suite(benchmark_results, baseline)
            benchmark_results["_regression"] = regression
            if stop_on_regression and not regression["all_pass"]:
                benchmark_results["_all_pass"] = False

        results_path.write_text(
            self._format_results(benchmark_results, output_format), encoding="utf-8"
        )

        if ratchet and benchmark_results.get("_all_pass"):
            self._ratchet(benchmark_results, output_format)

        # Merge benchmark results at the top level for backward compatibility.
        results.update(benchmark_results)
        results["benchmark"] = benchmark_results
        results["_all_pass"] = static_all_pass and benchmark_results.get("_all_pass", False)
        return results

    def _ratchet(self, results: Dict[str, Any], output_format: str) -> None:
        """Copy current results to the baseline path."""
        if not self.baseline_path:
            return
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self.baseline_path.write_text(
            self._format_results(results, output_format), encoding="utf-8"
        )

    @staticmethod
    def _format_results(results: Dict[str, Any], fmt: str) -> str:
        fmt = fmt.lower()
        if fmt == "json":
            return json.dumps(results, indent=2, ensure_ascii=False)
        return cast(str, yaml.safe_dump(results, allow_unicode=True, sort_keys=False))


def run_ci_pipeline(
    skill: str,
    registry_path: Path,
    baseline_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    config_path: Optional[Path] = None,
    level: Optional[int] = None,
    suite: Optional[str] = None,
    ratchet: bool = False,
    stop_on_regression: bool = True,
    output_format: str = "yaml",
    static_only: bool = False,
    run_benchmark: bool = True,
    run_smoke: bool = True,
    run_deps: bool = True,
    run_deps_dry_run: bool = False,
    code_path: Optional[Path] = None,
    results_mode: bool = True,
) -> Dict[str, Any]:
    """Convenience wrapper around ``CIPipeline.run``."""
    pipeline = CIPipeline(
        skill=skill,
        registry_path=registry_path,
        baseline_path=baseline_path,
        output_dir=output_dir,
        config_path=config_path,
    )
    return pipeline.run(
        level=level,
        suite=suite,
        ratchet=ratchet,
        stop_on_regression=stop_on_regression,
        output_format=output_format,
        static_only=static_only,
        run_benchmark=run_benchmark,
        run_smoke=run_smoke,
        run_deps=run_deps,
        run_deps_dry_run=run_deps_dry_run,
        code_path=code_path,
        results_mode=results_mode,
    )
