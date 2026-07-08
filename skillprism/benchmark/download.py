#!/usr/bin/env python3
"""Data download utilities for benchmarks."""

from __future__ import annotations

import hashlib
import importlib
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


def _checksum(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_url(url: str, dest: Path, expected_checksum: Optional[str] = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and expected_checksum and _checksum(dest) == expected_checksum:
        return dest

    print(f"Downloading {url} ...")
    urllib.request.urlretrieve(url, dest)

    if expected_checksum and _checksum(dest) != expected_checksum:
        raise ValueError(f"Checksum mismatch for {url}")
    return dest


def load_builtin(source: str) -> Any:
    """Load a builtin dataset from a Python expression like 'scanpy.datasets.pbmc3k_processed'."""
    module_name, attr_name = source.rsplit(".", 1)
    module = importlib.import_module(module_name)
    fn = getattr(module, attr_name)
    return fn()


def fetch_dataset(dataset_spec: Dict[str, Any], cache_dir: Path) -> Any:
    dtype = dataset_spec.get("type", "builtin")
    if dtype == "builtin":
        return load_builtin(dataset_spec["source"])
    if dtype == "url":
        url = dataset_spec["source"]
        filename = url.split("/")[-1].split("?")[0] or "data"
        dest = cache_dir / filename
        checksum = dataset_spec.get("checksum")
        download_url(url, dest, checksum)
        return dest
    if dtype == "local":
        return Path(dataset_spec["source"])
    raise ValueError(f"Unsupported dataset type: {dtype}")
