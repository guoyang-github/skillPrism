#!/usr/bin/env bash
# Quickstart: end-to-end skillPrism workflow for the csv-summary skill.
set -euo pipefail

cd "$(dirname "$0")"

REGISTRY="benchmarks/csv-summary/registry.yaml"

echo "== 1. Static rubric evaluation =="
skill-pipeline \
    --intent evaluate \
    --skills-dir skills \
    --engine-dir . \
    --output quickstart-report.md

echo ""
echo "== 2. CI static gate =="
skill-ci \
    --skill csv-summary \
    --registry "$REGISTRY" \
    --output-format markdown

echo ""
echo "== 3. Dynamic benchmark with generated skill code =="
skill-ci \
    --skill csv-summary \
    --registry "$REGISTRY" \
    --run-benchmark \
    --code sample_skill_code.py \
    --output-format yaml

echo ""
echo "== 4. Gradual pipeline (level 0 unit/boundary gate) =="
skill-gradual \
    --skill csv-summary \
    --registry "$REGISTRY" \
    --max-level 0 \
    --no-ratchet

echo ""
echo "Quickstart complete. Inspect the generated reports in:"
echo "  - quickstart-report.md"
echo "  - artifacts/csv-summary/ci/report.*"
echo "  - artifacts/csv-summary/ci/gradual/"
