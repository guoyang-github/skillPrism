.PHONY: install install-dev test coverage lint format clean docs-ci docs-serve docs-build docs-deploy

PYTHON ?= python

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -q

coverage:
	$(PYTHON) -m pytest tests/ --cov=skillprism --cov-report=term-missing --cov-report=html

lint:
	$(PYTHON) -m ruff check .

type-check:
	$(PYTHON) -m mypy skillprism

format:
	$(PYTHON) -m ruff format .

format-check:
	$(PYTHON) -m ruff format --check .

docs-ci:
	evaluate-skill --all --skills-dir ./skills --config skill_rubric_types.yaml --output docs/SKILL_SCORECARD.md --run-smoke
	test-skill --mode single --skill document-demo \
	    --registry examples/benchmark_minimal/benchmarks/document-demo/registry.yaml \
	    --code examples/benchmark_minimal/sample_document_skill_code.py \
	    --output /tmp/document_benchmark_result.yaml

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name htmlcov -exec rm -rf {} +
	find . -type d -name .benchmark_cache -exec rm -rf {} +
	find . -type d -name site -exec rm -rf {} +

docs-serve:
	$(PYTHON) -m mkdocs serve

docs-build:
	$(PYTHON) -m mkdocs build

docs-deploy:
	$(PYTHON) -m mkdocs gh-deploy
