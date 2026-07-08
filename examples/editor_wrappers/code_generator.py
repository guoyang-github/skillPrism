#!/usr/bin/env python3
"""Example code generator wrapper using an LLM via subprocess.

This is a minimal example. In production you would connect to your preferred
LLM provider (OpenAI, Anthropic, local vLLM, Ollama, etc.).

Expected usage:
    export SKILLPRISM_CODE_GENERATOR_COMMAND="python examples/editor_wrappers/code_generator.py"
    python scripts/skill_code_generator.py skills/my-skill \
        --registry benchmarks/my-skill/registry.yaml \
        --benchmark my_bench \
        --output benchmarks/my-skill/runner.py

The command reads a prompt from stdin and prints generated code to stdout.
"""

from __future__ import annotations

import sys


def main() -> int:
    prompt = sys.stdin.read()

    # In a real implementation, send `prompt` to an LLM and return the code.
    # This minimal fallback returns a hard-coded table summary script so that
    # the generator framework can be tested without an API key.
    if "table" in prompt.lower() and "input_csv" in prompt:
        code = """import pandas as pd

df = pd.read_csv(input_csv)
summary = df.describe()
summary.to_csv(output_csv)
"""
    elif "clustering" in prompt.lower() and "adata" in prompt:
        code = """import scanpy as sc

sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.5)
adata.write_h5ad(output_path if 'output_path' in dir() else 'output.h5ad')
"""
    else:
        code = (
            "# TODO: replace this placeholder with LLM-generated code\n"
            "# The prompt was:\n" + "# " + prompt.replace("\n", "\n# ")
        )

    print(code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
