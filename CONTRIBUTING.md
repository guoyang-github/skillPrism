# Contributing to skillPrism

Thank you for helping improve skillPrism! This document outlines the workflow
and standards we follow.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/nanobot-skills/Skills_Validation.git
cd Skills_Validation

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Optional: install pre-commit hooks
pre-commit install
```

## Running Tests

```bash
make test
```

Or with coverage:

```bash
make coverage
```

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
make lint        # check for issues
make format      # auto-format code
make format-check # verify formatting without changing files
```

Pre-commit hooks will run the same checks automatically.

## Adding a New Skill Type

1. Edit `skill_rubric_types.yaml` and add a new entry under `skill_types`.
2. If the type needs custom checks, add a small function in
   `skillprism/evaluate_skill_rubric.py` and wire it into the dimension evaluator.
3. Add unit tests in `tests/`.
4. Update the README and documentation.

## Working with Markdown Structure

The `skillprism/markdown_structure.py` module parses `SKILL.md` files into
headers, code blocks, tables, and frontmatter.  Dimension evaluators use it for
section-aware keyword matching.  If you add a new structural heuristic:

1. Add the helper to `skillprism/markdown_structure.py`.
2. Add unit tests in `tests/test_markdown_structure.py`.
3. Prefer section-aware checks over whole-document substring matching.

## Adding a Benchmark

1. Create a benchmark entry in your project's registry YAML.
2. Provide a runner (`<bench>/runner.py`) or rely on the built-in task runners.
3. Provide expected/golden output when applicable.
4. Run `test-skill --mode single` to verify it passes.

See `examples/quickstart/` for a minimal, runnable benchmark that exercises the
rubric, CI gate, dynamic benchmark, and gradual pipeline without requiring an
external agent.

## Pull Request Checklist

- [ ] `make test` passes locally.
- [ ] `make lint` passes locally.
- [ ] New functionality is covered by tests.
- [ ] Documentation (README, SKILL.md, playbooks) is updated.
- [ ] No new large files are committed (use `pre-commit` to catch this).

## Reporting Issues

Please include:

- Python version
- Installation method (`pip install -e .` or wrapper scripts)
- Minimal command to reproduce the issue
- Expected vs actual output
