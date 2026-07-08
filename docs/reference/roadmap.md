# TODO & Roadmap

This document tracks completed milestones and known improvement opportunities
for skillPrism.

---

## ✅ Completed (as of current version)

- [x] Deterministic rubric engine with 9 dimensions (D1–D9).
- [x] Project-agnostic type registry via `skill_rubric_types.yaml`.
- [x] Installable Python package (`skillprism`) with CLI entrypoints.
- [x] Optional LLM-as-judge for subjective dimensions (D2/D5) with:
  - provider-agnostic subprocess/caller interface,
  - JSON schema validation,
  - retry logic,
  - score clamping,
  - outlier protection against engine score.
- [x] Benchmark framework supporting `clustering`, `table`, and `document` tasks.
- [x] Real, runnable `document` benchmark in `examples/benchmark_minimal/` using a
deterministic SKILL.md generator.
- [x] Human-in-the-loop optimization loop via `improve-skill` with dry-run judge,
  `--apply` gate, anti-pattern guards, and `--ratchet` mode.
- [x] Quality pipeline orchestrator (`skill-pipeline` CLI) with multiple intents.
- [x] Agent-native SKILL.md entries and an `Agent Interaction Guide`.
- [x] `pytest` test suite (140+ tests).
- [x] English and Chinese READMEs, operational playbook, and scorecard examples.
- [x] Benchmark `suite` grouping and `expected_result: fail` negative tests.
- [x] Structured JSON/YAML/Markdown benchmark output.
- [x] Intelligent optimization loop with dimension priority, clusters, and
  `--stop-on-regression`.
- [x] End-to-end optimize test exercising baseline → edit → judge → keep.
- [x] Custom benchmark task plugin API via entry points and registry plugins.
- [x] Per-type `SKILL.md` templates for `analysis`, `cmd`, `api`, `document`.
- [x] Judge report renders SKILL.md diff and exports it to JSON.
- [x] `--edit-code` flag allows auto-edit to modify code assets with snapshot/rollback.
- [x] MkDocs static documentation site with Material theme.
- [x] Book-style 8-chapter tutorial under `docs/tutorial/`.
- [x] `skillprism.testing` module with mock data and boundary-case helpers.
- [x] Benchmark framework enhancements: `level` (0-3), `requires_gpu`, `real_data`, suite regression.
- [x] `skillprism.ci` module with `skill-ci` CLI (run, compare, ratchet, stop-on-regression).
- [x] Gradual failure-mode-first pipeline with `test-skill --mode gradual` CLI, integrated into `skills/skill-prism/SKILL.md`.
- [x] End-to-end cell2location example with level 0-3 benchmarks.
- [x] Orchestrator `--intent "run gradual pipeline"` integration.
- [x] MIT license.
- [x] Engineering tooling:
  - `ruff` lint/format configuration,
  - `pytest-cov` coverage configuration,
  - `pre-commit` hooks,
  - `Makefile`,
  - `CONTRIBUTING.md`,
  - GitHub Actions CI workflow with multi-Python matrix.
- [x] `mypy --strict` type checking across `skillprism/`.
- [x] Per-skill-type `enabled_dimensions` and a dedicated `meta` skill type for
  framework-level skills.
- [x] LLM judge reproducibility metadata (`model`, `temperature`, `prompt_version`)
  and configurable per-dimension prompt templates.
- [x] `scripts/langfuse_to_benchmark.py` to generate benchmark entries from
  Langfuse traces.

---

## 📋 Short-Term Backlog

### Benchmarks & Real-World Validation

- [x] Add a real `deconvolution` benchmark example with synthetic and real-data
levels (`examples/benchmark_cell2location/`).
- [ ] Add a real `clustering` benchmark with downloadable scRNA-seq data and
golden labels (the current example uses `scanpy.datasets.pbmc3k_processed`).
- [ ] Add a real `table` benchmark with a CSV input and expected output.
- [ ] Add at least one domain-specific benchmark outside genomics (e.g., SQL
query generation, API orchestration).
- [x] Provide a `build-skill-test` step-by-step example in `docs/tutorial/`.

### LLM-as-Judge Hardening

- [x] Single optional LLM judge with schema validation, retries, and outlier
protection.
- [x] Multi-judge consensus with configurable `n_judges` and aggregation
  (`median`, `mean`, `min`, `max`).
- [ ] Add LLM judge calibration against a small human-annotated set.
- [ ] Add prompt-injection / adversarial-output detection.
- [ ] Add per-dimension weight overrides.
- [ ] Capture and expose LLM judge latency/cost metrics.

### Optimization Loop

- [x] Provide `--auto-edit` as the optional turnkey autonomous optimizer
(completed). The engine stays LLM-free; the editor is an external,
provider-agnostic command.
- [x] Add `--max-rounds` automatic iteration for `--auto-edit`.
- [x] Add per-dimension editing strategy templates (D1–D9).
- [x] Provide example editor wrappers for OpenAI, Anthropic, and Ollama.
- [x] Add an end-to-end test exercising `--record-baseline`, edit, `--judge`,
  and `--apply` keep/revert.
- [x] Add automatic diff rendering in the judge report.
- [x] Add a `--max-rounds` guard and a `--stop-on-regression` option.
- [x] Support editing code assets behind an explicit `--edit-code` flag with
additional smoke/benchmark gates.

### Skill Entry Layer

- [ ] Add interactive confirmation wrappers for agent use (e.g., `ask_user`
helpers).
- [x] Add per-skill `SKILL.md` templates for each built-in type (`analysis`,
`cmd`, `api`, `document`).
- [ ] Add a judge result parser helper so agents can consume the
engine output programmatically.
- [ ] Provide example `scripts/my_skill_editor.py` wrappers for common LLM
providers (OpenAI, Anthropic, local vLLM/ollama).

---

## 🚀 Mid-Term Roadmap

- [ ] **CI/CD dogfooding**: run skillPrism on its own repository in every CI
build and fail the build if any skill regresses.
- [ ] **Type hints**: achieve full `mypy --strict` coverage across `skillprism/`.
- [x] **Documentation website**: move from Markdown files to a static site
(MkDocs or similar) with search.
- [x] **Searchable API reference**: auto-generate API docs from docstrings.
- [ ] **Registry versioning**: version `skill_rubric_types.yaml` and provide
migration notes between schema versions.
- [x] **Plugin API**: allow third-party packages to register new benchmark tasks
and rubric checks via entry points.
- [ ] **More plugin hooks**: allow plugins to register new rubric dimensions and
  skill-type detectors.
- [ ] **Web dashboard**: visualize scorecard history and benchmark trends.

---

## 🔬 Research / Validation

- [ ] Correlate rubric scores with human judgments on a representative skill
corpus (Spearman / Kendall).
- [ ] Study the impact of `--llm-judge` on D2/D5 correlation with human scores.
- [ ] Compare `--auto-edit` with a user-provided LLM editor against manual
Agent editing on a shared set of skills.

---

## How to Pick Up an Item

1. Open an issue describing the item and your proposed approach.
2. Discuss the design briefly to avoid wasted effort.
3. Implement with tests and documentation updates.
4. Ensure `make test` and `make lint` pass.
5. Submit a pull request referencing this roadmap.
