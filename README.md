# skillPrism

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A project-agnostic Python framework for evaluating, benchmarking, and optimizing AI agent skills.

skillPrism separates **measurement** (the engine) from **LLM-driven editing** (the skill/agent layer). It provides:

- A configurable 9-dimension rubric for static skill quality.
- A benchmark registry for task-level correctness (clustering, table, document generation, etc.).
- CLI tools and a Python API.
- Human-in-the-loop optimization workflow via companion skills.

For the Chinese README, see [README.md](README.md).

> Want to understand the whole system first? Read [`docs/OVERVIEW.md`](docs/OVERVIEW.md).

---

## Table of Contents

- [Architecture](#architecture)
- [Design Principles](#design-principles)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
- [Skill Types](#skill-types)
- [Rubric Dimensions](#rubric-dimensions)
- [Benchmarks](#benchmarks)
- [Optimization Workflow](#optimization-workflow)
- [Quality Pipeline](#quality-pipeline)
- [Relationship to darwin-skill](#relationship-to-darwin-skill)
- [Project Structure](#project-structure)
- [License](#license)

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

**Core principles**: the engine has no LLM dependency, measurements are reproducible, the default is dry-run, and `--apply` is required before any file is modified.

For a full architectural overview, see [`docs/OVERVIEW.md`](docs/OVERVIEW.md).

---

## Design Principles

1. **Engine has no LLM dependency.**
   Rubric scoring, benchmark execution, and regression checks are deterministic measurements. Any LLM usage happens inside skills/agents, not in `skillprism`.

2. **Skills are the user interface.**
   After installing `skillprism`, users can drive the whole workflow through natural language via the `skill-prism` skill.

3. **Human remains in control.**
   The engine can measure and suggest, but editing code assets or final acceptance requires explicit human approval by default.

4. **Project-agnostic.**
   Types, weights, thresholds, and checks are defined in `skill_rubric_types.yaml`. Point `--skills-dir` and `--config` at any project.

---

## Quick Start

### Install

```bash
pip install -e .
```

Optional benchmark dependencies:

```bash
pip install -e ".[all]"          # security + dev
pip install sentence-transformers  # semantic document similarity
pip install rouge-score            # ROUGE-L document metric
pip install bert-score             # BERTScore document metric
```

### Evaluate one skill

```bash
evaluate-skill skills/bio-single-cell-clustering --detailed
```

### Evaluate all skills

```bash
evaluate-skill --all \
    --skills-dir ./skills \
    --config skill_rubric_types.yaml \
    --output docs/SKILL_SCORECARD.md \
    --run-smoke
```

### Run a benchmark

```bash
test-skill --mode single --skill document-demo \
    --registry examples/benchmark_minimal/benchmarks/document-demo/registry.yaml \
    --code examples/benchmark_minimal/sample_document_skill_code.py \
    --output /tmp/result.yaml
```

The `document-demo` benchmark in `examples/benchmark_minimal/document_benchmark/` is a
real, runnable document-generation task. It reads a prompt from `prompt.txt`, uses a
deterministic generator (`generator.py`, no LLM required) to produce a SKILL.md, and
compares it to the golden reference `expected/best_skill.md` using structural,
lexical, length, and optional semantic/ROUGE-L/BERTScore metrics.

### Build a new benchmark

```bash
build-skill-test \
    --id skill_md_generation \
    --name "SKILL.md Generation" \
    --skill-type document \
    --task document \
    --dataset-source prompts/write_skill_md.txt \
    --expected-path expected/best_skill.md \
    --registry benchmarks/<skill>/registry.yaml
```

---

## CLI Commands

After installation, the following commands are available:

| Command | Purpose |
|---|---|
| `evaluate-skill` | Run rubric evaluation on one or all skills. |
| `test-skill --mode single|gradual|quick` | Run benchmarks for a skill from a registry. |
| `build-skill-test` | Scaffold a new benchmark registry entry. |
| `skill-pipeline` | Run the full quality pipeline (rubric + benchmark + report). |

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

Each type can override dimension names, weights, and checks.

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

Weights and thresholds are configurable in `skill_rubric_types.yaml`.

---

## Benchmarks

Benchmarks answer "does the skill actually run correctly?" Rubrics answer "is the skill well-written?". They complement each other.

Supported tasks:

- `clustering`: scRNA-seq clustering (requires `scanpy`, `scikit-learn`)
- `table`: CSV table metrics
- `document`: text/document generation quality

### Document benchmark metrics

| Metric | Meaning |
|---|---|
| `section_overlap` | Ratio of expected markdown headers present in output |
| `token_jaccard` | Word-level Jaccard similarity |
| `length_ratio` | `len(output) / len(expected)` |
| `semantic_similarity` | Sentence-embedding cosine similarity (optional) |
| `rouge_l` | ROUGE-L F-measure (optional) |
| `bert_score_f1` | BERTScore F1 (optional) |

Optional metrics are only computed when listed in the registry and skip gracefully if their libraries are not installed.

---

## Optimization Workflow

`skillprism` provides measurement and judgment. The editing step can be handled in two ways:

| Mode | How it edits | Best for |
|---|---|---|
| Manual / Agent (default) | Agent / user edits `SKILL.md` manually; skillprism measures and rolls back | Manual or agent-guided iteration with human review of every diff |
| `--auto-edit` | `improve-skill ... --auto-edit --apply` | Fully autonomous analyze → edit → judge → keep/revert loop |

**Independence**: `skillprism` does not depend on any external skill or LLM provider. The optional `--auto-edit` mode calls a user-provided editor command (which may use an LLM), while the engine itself stays LLM-free.

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
export SKILLPRISM_EDITOR_COMMAND="python scripts/my_skill_editor.py"

improve-skill skills/<skill> \
  --record-baseline \
  --benchmark-registry benchmarks/<skill>/registry.yaml \
  --auto-edit \
  --apply \
  --max-rounds 3
```

- `--auto-edit` rewrites `SKILL.md`, so it requires `--apply` to actually run the edit + judge + keep/revert cycle.
- `--max-rounds N` iterates up to N rounds, using each kept edit as the new baseline for the next round.
- Ready-to-use wrappers for common providers are in `examples/editor_wrappers/`:
  - `openai_editor.py`
  - `anthropic_editor.py`
  - `ollama_editor.py`

### Safety features

- `--judge` is a **dry-run** by default; it prints the decision but does not keep or revert.
- `--apply` is required to actually enforce the decision.
- Anti-pattern guards run automatically and warn/block on:
  - one round changing multiple dimensions
  - dry-run ratio > 30%
  - `git reset --hard` in docs/scripts
  - SKILL.md bloat without score gain
  - same model editing and judging
- `--ratchet` ensures the score never drops below the historical best.

By default, only `SKILL.md` is edited. Editing code assets (`scripts/`, `examples/`, `requirements.txt`) requires explicit authorization and additional gates.

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
- The engine remains deterministic and provider-agnostic; the LLM is just an optional plugin.
- Configure `weight`, `max_retries`, `outlier_threshold`, and `require_reason` in the
  `llm_judge` section of `skill_rubric_types.yaml`.

---

## Quality Pipeline

`skill-pipeline` chains everything into one command:

```bash
skill-pipeline --intent "run full quality pipeline" \
    --skills-dir ./skills \
    --benchmark-registry ./benchmarks/<skill>/registry.yaml \
    --output docs/SKILL_QUALITY_REPORT.md \
    --run-smoke
```

```bash
# Identify the worst skill and prepare optimization
skill-pipeline --intent "optimize skills" \
    --skills-dir ./skills \
    --benchmark-registry ./benchmarks/<skill>/registry.yaml

# If SKILLPRISM_EDITOR_COMMAND is configured, the report will include the
# corresponding --auto-edit --apply command for the worst skill.
```

Supported intents:

- `"evaluate all skills"`: rubric only
- `"run benchmarks"`: benchmarks + baseline comparison
- `"run full quality pipeline"`: rubric → benchmark → worst-skill report
- `"optimize skills"`: pipeline → record baseline for worst skill → provide next judge command

If `SKILLPRISM_EDITOR_COMMAND` is configured, you can switch the suggested next command to `--auto-edit --apply` for a fully autonomous optimization round.

---

## Agent-Native Skill Entry

`skills/skill-prism/references/AGENT_GUIDE.md` defines a standard interaction protocol for agents using
skillPrism: greeting templates, approval checkpoints, diff display, failure
recovery, and final report format. The single agent entry point is:

- `skills/skill-prism/SKILL.md` — covers evaluate / test / build-skill-test / improve / pipeline / CI intents.

---

## Engineering Tooling

```bash
# Development install
pip install -e ".[dev]"

# Run tests
make test

# Coverage report
make coverage

# Lint and format
make lint
make format

# CI-style rubric + benchmark run
make docs-ci
```

Configured out of the box:

- `pyproject.toml`: pytest, coverage, and ruff settings.
- `.pre-commit-config.yaml`: ruff + basic hooks + local pytest.
- `.github/workflows/skill-rubric-ci.yaml`: multi-Python matrix with lint/test/rubric/benchmark/security jobs.
- `CONTRIBUTING.md`: setup, PR checklist, and style guide.

---

## Relationship to darwin-skill

[darwin-skill](https://github.com/alchaincyf/darwin-skill) is an excellent *skill* that runs inside an agent tool (Claude Code, etc.) and optimizes other skills with a human-in-the-loop, multi-judge, validation-gated workflow. skillprism absorbs several of those safety ideas (dry-run judge, anti-pattern guards, ratchet, benchmark gating) while remaining a fully independent engine-first framework.

**Key difference**: skillprism does **not** depend on darwin-skill. The optional `--auto-edit` mode calls a user-provided editor command, which can be any LLM wrapper, agent tool, or even a deterministic generator. The engine itself stays LLM-free and provider-agnostic.

Use **skillPrism** when you need:
- A reusable, installable evaluation engine.
- Deterministic rubric scoring and benchmark gates.
- CI integration without external skill dependencies.
- Independence from any particular agent tool or LLM provider.

Use **darwin-skill** directly if you specifically want its proven agent-native optimizer inside a supported agent tool.

---

---

## Project Structure

```
Skills_Validation/
├── skillprism/                 # Python engine
│   ├── evaluate_skill_rubric.py
│   ├── optimize_skill.py
│   ├── gradual.py              # failure-mode-first staged pipeline
│   ├── rubric_enhancements.py
│   ├── experiment_history.py
│   ├── optimization_strategy.py
│   ├── dimension_clusters.py
│   ├── runtime_neutrality.py
│   ├── security_evaluator.py
│   ├── smoke_test_runner.py
│   ├── dependency_checker.py
│   ├── skill_lens_checks.py
│   ├── benchmark/
│   │   ├── runner.py
│   │   ├── builder.py
│   │   ├── metrics.py
│   │   ├── regression.py
│   │   └── plugins.py
│   ├── ci/
│   ├── testing/
│   └── orchestrator.py
├── skill_rubric_types.yaml     # Type and rubric configuration
├── skills/                     # Agent-facing skill entry
│   ├── skill-prism/
│   │   └── SKILL.md
│   └── AGENT_GUIDE.md          # Agent interaction protocol
├── benchmarks/                 # Per-skill benchmark registry
│   └── <skill>/
│       ├── registry.yaml
│       └── tasks/
│           └── <task>.yaml
├── examples/                   # Minimal benchmark example
├── tests/                      # pytest unit tests
├── docs/                       # Documentation
│   ├── reference/
│   │   ├── overview.md         # System overview (start here)
│   │   ├── framework.md
│   │   ├── operational-playbook.md
│   │   ├── benchmark-guide.md
│   │   ├── gradual-testing.md
│   │   ├── rubric-enhancements.md
│   │   ├── optimization-strategy.md
│   │   ├── experiment-history.md
│   │   ├── runtime-neutrality.md
│   │   ├── cell2location.md
│   │   └── roadmap.md
│   ├── getting-started/
│   └── tutorial/
├── LICENSE                     # MIT
└── pyproject.toml
```

---

## License

[MIT](LICENSE)
