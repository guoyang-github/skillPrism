# skillPrism Quickstart

This directory contains a minimal, end-to-end skillPrism workflow that can be run
without an LLM or external agent.  It uses a simple `csv-summary` skill and a
document-generation benchmark to demonstrate:

1. Static rubric evaluation
2. CI static gate
3. Dynamic benchmark with pre-generated skill code
4. Gradual (failure-mode-first) pipeline level 0

## Directory Layout

```
examples/quickstart/
├── skills/csv-summary/SKILL.md         # The skill being evaluated
├── skills/csv-summary/test-prompts.json
├── benchmarks/csv-summary/
│   ├── registry.yaml                   # Per-skill benchmark registry
│   ├── tasks/document.yaml             # Benchmark task specification
│   ├── data/csv_summary.txt            # Prompt for the document benchmark
│   └── expected/csv_summary.md         # Expected output for the benchmark
├── sample_skill_code.py                # Deterministic skill-code artifact
└── run_quickstart.sh                   # One-script end-to-end demo
```

## Prerequisites

- skillPrism installed in the active Python environment
- Bash (for the runner script)

## Run It

```bash
cd examples/quickstart
bash run_quickstart.sh
```

The script will create:

- `quickstart-report.md` — rubric scorecard for `csv-summary`
- `ci-output/report.*` — CI gate report (static and dynamic)
- `gradual-output/` — gradual stage artifacts

## What Each Step Does

### 1. Static rubric evaluation

```bash
skill-pipeline --intent evaluate --skills-dir skills --output quickstart-report.md
```

Scores the skill against the built-in rubric (D1–D9).  No code execution or LLM
calls are made.

### 2. CI static gate

```bash
skill-ci --skill csv-summary \
    --registry benchmarks/csv-summary/registry.yaml \
    --output-dir ci-output
```

Runs rubric, smoke, dependency, and security checks.

### 3. Dynamic benchmark

```bash
skill-ci --skill csv-summary \
    --registry benchmarks/csv-summary/registry.yaml \
    --run-benchmark --code sample_skill_code.py \
    --output-dir ci-output
```

Executes `sample_skill_code.py` in a sandbox and compares the generated
`SKILL.md` against `benchmarks/csv-summary/expected/csv_summary.md`.

### 4. Gradual pipeline

```bash
skill-gradual --skill csv-summary \
    --registry benchmarks/csv-summary/registry.yaml \
    --output-dir gradual-output --max-level 0 --no-ratchet
```

Runs the cheapest failure-mode-first stage (unit/boundary) without updating
baselines.

## Adapting to Your Own Skill

1. Copy `skills/csv-summary/` and rename it.
2. Create `benchmarks/<your-skill>/registry.yaml` for your skill.
3. Write a task spec under `benchmarks/<your-skill>/tasks/<task>.yaml`.
4. Provide a `sample_skill_code.py` that implements the task deterministically,
   or run in `--results` mode after an agent has produced output.
5. Run `bash run_quickstart.sh` again.
