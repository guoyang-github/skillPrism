#!/usr/bin/env python3
"""Backward-compatible wrapper for skillPrism.optimize_skill."""

from skillprism.optimize_skill import main

if __name__ == "__main__":
    raise SystemExit(main())
