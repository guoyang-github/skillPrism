# skillPrism

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A project-agnostic Python framework for evaluating, benchmarking, and optimizing AI agent skills.
>
> 中文 README: [README_CN.md](README_CN.md)
>
> Want to understand the whole system first? Read [`docs/reference/overview.md`](docs/reference/overview.md).

skillPrism separates **measurement** (the engine) from **LLM-driven editing** (the skill/agent layer). It provides:

- A configurable 9-dimension rubric for static skill quality.
- A benchmark registry for task-level correctness (clustering, table, document generation, etc.).
- A human-in-the-loop optimization loop: baseline → suggest → edit → judge → keep/revert (dry-run by default, `--apply` to modify files).
- CI quality gates: ratchet against historical best, regression comparison, multi-Python workflow template.
- An agent-native entry: copy `skills/skill-prism/` into your agent's skills directory and drive the whole workflow in natural language.

---

## Architecture

skillPrism is organized into three layers:

```
Skill entry layer (natural language)
  skills/skill-prism/SKILL.md  → "evaluate / test / improve / pipeline / CI"
               │
               ▼
Optional capability layer (user-selected)
  - SKILL.md editor command (--auto-edit)
  - LLM-as-judge command (--llm-judge)
               │
               ▼
Engine layer (skillprism Python package, no LLM dependency)
  evaluate_skill_rubric.py     → 9-dimension rubric scoring
  optimize_skill.py            → baseline / judge / rollback
  benchmark/runner.py          → benchmark registry and execution
  orchestrator.py              → quality pipeline orchestration
```

**Design principles**:

1. **Engine has no LLM dependency** — rubric scoring, benchmark execution, and regression checks are deterministic measurements. Any LLM usage lives in skills/agents or user-provided commands.
2. **Skills are the user interface** — after installing `skillprism`, users drive the workflow in natural language via the `skill-prism` skill.
3. **Human remains in control** — the engine measures and suggests; editing assets and final acceptance require explicit human approval by default.
4. **Project-agnostic** — types, weights, thresholds, and checks are defined in `skill_rubric_types.yaml`. Point `--skills-dir` and `--config` at any project.

For a full architectural overview, see [`docs/reference/overview.md`](docs/reference/overview.md).

---

## Quick Start

### Install

```bash
pip install -e .
pip install -e ".[all]"          # optional: security + dev
pip install -e ".[benchmark]"    # optional: benchmark extras (scanpy, scikit-learn, etc.)
```

### Evaluate one skill

```bash
evaluate-skill skills/bio-single-cell-clustering --detailed
```

### Evaluate all skills

```bash
evaluate-skill --all \
    --skills-dir ./skills \
    --output reports/SKILL_SCORECARD.md \
    --run-smoke
```

### Run a benchmark

```bash
test-skill --mode single --skill document-demo \
    --registry examples/benchmark_minimal/benchmarks/document-demo/registry.yaml \
    --code examples/benchmark_minimal/sample_document_skill_code.py
```

The `document-demo` benchmark in `examples/benchmark_minimal/` is a real, runnable
document-generation task: `benchmarks/document-demo/data/prompt.txt` holds the prompt,
`sample_document_skill_code.py` is a deterministic generator (no LLM required) that
produces a SKILL.md, and the output is compared to the golden reference
`benchmarks/document-demo/expected/best_skill.md` using structural, lexical, length,
and optional semantic/ROUGE-L/BERTScore metrics.

### Build a new benchmark

```bash
build-skill-test \
    --id skill_md_generation \
    --name "SKILL.md Generation" \
    --skill my-skill \
    --task document \
    --input prompts/write_skill_md.txt \
    --expected-path expected/best_skill.md \
    --registry benchmarks/my-skill/registry.yaml
```

---

## CLI Commands

After installation, the following commands are available:

| Command | Purpose |
|---|---|
| `evaluate-skill` | Run rubric evaluation on one or all skills. |
| `test-skill --mode single\|gradual\|quick` | Run benchmarks: single-level / failure-first gradual / quick. |
| `build-skill-test` | Scaffold a new benchmark registry entry. |
| `improve-skill` | Optimization loop: baseline / suggest / judge / rollback (no LLM calls by itself). |
| `skill-pipeline` | Run the full quality pipeline (rubric + benchmark + report). |
| `skill-ci` | CI quality gates. |
| `skill-gradual` | Convenience wrapper for `test-skill --mode gradual`. |

---

## Skill Types

`skill_rubric_types.yaml` defines five built-in types:

| Type | Use case |
|---|---|
| `analysis` | Python/R data analysis skills |
| `cmd` | Shell/CLI/command-line skills |
| `api` | Database/REST API skills |
| `document` | Document generation / scientific writing / orchestration skills |
| `generic` | Fallback when no specific type fits |

Each type can override dimension names, weights, and checks. To add a new type, add an
entry under `skill_types` — file-existence and keyword checks need no engine changes
(see [`docs/reference/framework.md`](docs/reference/framework.md)).

---

## Rubric Dimensions

| Dim | Weight | Meaning |
|---|---|---|
| D1 | 0.10 | Structure and metadata |
| D2 | 0.15 | Documentation clarity |
| D3 | 0.18 | Executability / correctness |
| D4 | 0.12 | Environment reproducibility |
| D5 | 0.15 | Domain accuracy |
| D6 | 0.10 | LLM callability |
| D7 | 0.08 | Performance / resource / robustness |
| D8 | 0.04 | Maintainability |
| D9 | 0.08 | Security and trust |

Weights and thresholds are configurable in `skill_rubric_types.yaml`. Subjective
dimensions (D2, D5) rely on lightweight heuristics by default; treat them as quality
signals and combine with `--llm-judge` or human review for critical skills.

---

## Benchmarks

Benchmarks answer "does the skill actually run correctly?" Rubrics answer "is the skill well-written?". They complement each other.

Supported tasks:

- `clustering`: scRNA-seq clustering (requires `scanpy`, `scikit-learn`)
- `table`: CSV table metrics
- `document`: text/document generation quality

Design notes: `metrics` and `expected` live in the `registry.yaml` benchmark entry
(not in the task spec). Shared metric implementations are registered in
`skillprism/benchmark/metrics.py` via the `@metric("id")` decorator; each registry
directory may add a private `metrics.py`. Custom metrics:
see [`docs/reference/benchmark-metrics.md`](docs/reference/benchmark-metrics.md).

---

## Optimization Workflow

`skillprism` provides measurement and judgment. The editing step can be handled in two ways:

| Mode | How it edits | Best for |
|---|---|---|
| Manual / Agent (default) | Agent / user edits `SKILL.md` manually; skillprism measures and rolls back | Human review of every diff |
| `--auto-edit` | `improve-skill ... --auto-edit --apply` | Fully autonomous analyze → edit → judge → keep/revert loop |

By default only `SKILL.md` is edited. Editing code assets (`scripts/`, `examples/`,
`requirements.txt`) requires explicit authorization plus smoke-test / benchmark gates.

### Typical loop (manual / agent)

```bash
# 1. Record baseline
improve-skill skills/<skill> --record-baseline

# 2. Identify weakest dimension
improve-skill skills/<skill> --suggest

# 3. Agent edits SKILL.md with human approval

# 4. Judge (dry-run by default)
improve-skill skills/<skill> --judge

# 5. Apply the decision only after human confirmation
improve-skill skills/<skill> --judge --apply
```

### One-shot autonomous optimization (`--auto-edit`)

Configure any editor command that reads a prompt from stdin and prints the updated SKILL.md to stdout:

```bash
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"

improve-skill skills/<skill> \
  --record-baseline \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --auto-edit \
  --apply \
  --max-rounds 3
```

- `--auto-edit` rewrites `SKILL.md`, so it requires `--apply` to actually run the edit + judge + keep/revert cycle.
- `--max-rounds N` iterates up to N rounds, using each kept edit as the new baseline for the next round.
- Ready-to-use wrappers for common providers are in `examples/editor_wrappers/` (OpenAI / Anthropic / Ollama).

### Safety features

- `--judge` is a **dry-run** by default; it prints the decision but does not keep or revert. `--apply` is required to enforce it.
- Anti-pattern guards run automatically and warn/block on: one round changing multiple dimensions, dry-run ratio > 30%, `git reset --hard` in docs/scripts, SKILL.md bloat without score gain, same model editing and judging, silently skipped errors.
- `--ratchet` ensures the score never drops below the historical best (also available on `evaluate-skill`).

### Optional LLM-as-judge

For subjective dimensions (D2 documentation clarity, D5 domain accuracy), you can enable a second opinion from an LLM:

```bash
export SKILLPRISM_LLM_JUDGE_COMMAND="python scripts/my_llm_judge.py"

evaluate-skill skills/<skill> --detailed --llm-judge
improve-skill skills/<skill> --judge --llm-judge
```

The judge command reads a prompt from stdin and must print JSON:

```json
{"score": 4, "reason": "Clear examples and accurate domain guidance."}
```

- The engine score and LLM score are blended (default weight 30% LLM).
- The judge is defensive by default: JSON schema validation, score clamping to 1–5,
  retries on parse/schema failures, and outlier rejection when the LLM score deviates
  more than `outlier_threshold` (default 2) from the engine score.
- Configure `weight`, `max_retries`, `outlier_threshold`, and `require_reason` in the
  `llm_judge` section of `skill_rubric_types.yaml`.

---

## Quality Pipeline

`skill-pipeline` chains everything into one command:

```bash
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry ./benchmarks/<skill>/registry.yaml \
    --output reports/SKILL_QUALITY_REPORT.md \
    --run-smoke
```

Supported intents:

- `"evaluate all skills"`: rubric only
- `"run benchmarks"`: benchmarks + baseline comparison
- `"run full quality pipeline"`: rubric → benchmark → worst-skill report
- `"optimize skills"`: pipeline → record baseline for worst skill → provide next judge command

If `SKILLPRISM_EDITOR_COMMAND` is configured, the report will include the
corresponding `--auto-edit --apply` command for the worst skill.

---

## Agent-Native Skill Entry

Copy `skills/skill-prism/` into your agent's skills directory and drive the workflow in natural language:

| User intent | Engine command | Approval needed |
|---|---|---|
| "Evaluate all skills" | `evaluate-skill --all --skills-dir ./skills` | No |
| "Test bio-single-cell-clustering" | `test-skill --skill ... --task ...` | No |
| "Optimize bio-single-cell-clustering" | `improve-skill ... --record-baseline / --suggest / --judge` | **Yes** (every edit) |
| "Run the skill quality pipeline" | `skill-pipeline --intent "..."` | No |

`skills/skill-prism/references/AGENT_GUIDE.md` defines the standard interaction
protocol: greeting templates, approval checkpoints, diff display, failure recovery,
and final report format.

---

## Engineering Tooling

```bash
pip install -e ".[dev]"   # Development install
make test                 # Run tests
make coverage             # Coverage report
make lint && make format  # Lint and format
make docs-ci              # CI-style rubric + benchmark run
```

Configured out of the box: `pyproject.toml` (pytest, coverage, ruff, mypy),
`.pre-commit-config.yaml`, `.github/workflows/skill-rubric-ci.yaml` (multi-Python
matrix with lint/test/rubric/benchmark/security jobs), and `CONTRIBUTING.md`.

---

## Project Structure

```
Skills_Validation/
├── skillprism/                 # Python engine
│   ├── evaluate_skill_rubric.py
│   ├── optimize_skill.py
│   ├── gradual.py              # failure-mode-first staged pipeline
│   ├── rubric_enhancements.py
│   ├── optimization_strategy.py
│   ├── security_evaluator.py
│   ├── benchmark/              # runner / builder / metrics / plugins
│   ├── ci/
│   └── orchestrator.py
├── skill_rubric_types.yaml     # Type and rubric configuration
├── skills/skill-prism/         # Agent-facing skill entry
│   ├── SKILL.md
│   └── references/             # AGENT_GUIDE / LLM_JUDGE protocol docs
├── benchmarks/<skill>/         # Per-skill benchmark registry
├── examples/                   # Minimal benchmarks, cell2location demo, editor wrappers
├── templates/                  # Skill templates + regression test script
├── tests/                      # pytest unit tests
├── docs/                       # Documentation
│   ├── reference/              # Topic guides (overview.md is the entry point)
│   ├── getting-started/        # Install, CLI cheatsheet, per-command walkthroughs
│   └── tutorial/               # Step-by-step tutorials
├── LICENSE                     # MIT
└── pyproject.toml
```

---

## License

[MIT](LICENSE)
