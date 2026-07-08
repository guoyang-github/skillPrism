#!/usr/bin/env python3
"""Sandboxed execution of LLM-generated / agent-produced code.

The benchmark executors previously ran generated code with in-process ``exec()``,
giving untrusted code full access to the runner's privileges (filesystem, network,
secrets in ``os.environ``). This module runs such code in a **child process** with:

- a minimal environment (no inherited secrets/tokens);
- a dedicated working directory (``cwd`` jail to the output dir);
- ``resource.setrlimit`` caps on virtual memory (RLIMIT_AS), CPU seconds
  (RLIMIT_CPU), and writable file size (RLIMIT_FSIZE);
- a hard ``subprocess`` ``timeout``.

This is a process-level sandbox — it does not require a container runtime, which
keeps the dependency budget intact. Container-based isolation remains an
optional hardening layer documented separately.

``resource`` is Unix-only; on platforms without it the rlimits are skipped but
the subprocess isolation (separate process, minimal env, cwd jail, timeout)
still applies.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

try:  # Unix-only; degrade gracefully elsewhere
    import resource

    _HAS_RESOURCE = True
except ImportError:  # pragma: no cover - non-Unix platform
    _HAS_RESOURCE = False


def _set_rlimits(memory_mb: int, cpu_seconds: int, fsize_mb: int) -> None:
    """preexec_fn: cap memory/CPU/file-size in the child process."""
    if not _HAS_RESOURCE:
        return
    mem_bytes = memory_mb * 1024 * 1024
    fsize_bytes = fsize_mb * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except (ValueError, OSError):
        pass  # RLIMIT_AS unavailable on some platforms (e.g. macOS)
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
    except (ValueError, OSError):
        pass


# Inline wrapper: exposes resolved variables as globals, then execs the user
# script file. Kept as a ``-c`` string so no extra wrapper file is written.
_USER_CODE_WRAPPER = (
    "import os\n"
    "g = {'__name__': '__main__', 'output_dir': os.environ['OUTPUT_DIR']}\n"
    "for _k, _v in os.environ.items():\n"
    "    if _k.startswith('SKILLPRISM_VAR_'):\n"
    "        g[_k[len('SKILLPRISM_VAR_'):]] = _v\n"
    "with open(os.environ['SKILLPRISM_SCRIPT'], encoding='utf-8') as _f:\n"
    "    exec(compile(_f.read(), os.environ['SKILLPRISM_SCRIPT'], 'exec'), g)\n"
)

# Driver for a custom benchmark runner.py: loads it, calls run(...), and writes
# the returned output path to a known file so the parent can recover it.
_CUSTOM_RUNNER_DRIVER = (
    "import importlib.util, os\n"
    "from pathlib import Path\n"
    "spec = importlib.util.spec_from_file_location('runner', os.environ['SKILLPRISM_RUNNER'])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(m)\n"
    "_skill_code = ''\n"
    "_scp = os.environ.get('SKILLPRISM_SKILL_CODE_PATH', '')\n"
    "if _scp and os.path.exists(_scp):\n"
    "    with open(_scp, encoding='utf-8') as _f:\n"
    "        _skill_code = _f.read()\n"
    "_result = m.run(_skill_code, Path(os.environ['SKILLPRISM_INPUT_PATH']), Path(os.environ['SKILLPRISM_OUTPUT_DIR']))\n"
    "with open(os.path.join(os.environ['SKILLPRISM_OUTPUT_DIR'], '.skillprism_result'), 'w') as _f:\n"
    "    _f.write(str(_result))\n"
)


def _minimal_env(
    output_dir: Path, variables: Mapping[str, Any], extra: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Build a minimal child env: PATH/LANG/HOME only, plus resolved variables."""
    env = {
        "PATH": os.environ.get(
            "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        ),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "HOME": str(output_dir),
        "OUTPUT_DIR": str(output_dir),
        "MPLBACKEND": "Agg",
    }
    for k, v in variables.items():
        # Stash variables under a namespaced prefix; the wrapper re-exposes them
        # as top-level globals. Never copy the parent env wholesale.
        env[f"SKILLPRISM_VAR_{k}"] = str(v)
    if extra:
        env.update(extra)
    return env


def run_script_file(
    script_path: Path,
    *,
    timeout: int = 30,
    memory_mb: int = 512,
    cpu_seconds: int = 30,
    fsize_mb: int = 32,
) -> subprocess.CompletedProcess[str]:
    """Run an existing script file in a sandboxed child process.

    Used for smoke-testing a skill's example scripts: the script runs in a
    separate process with a minimal environment, a tmp cwd jail, and rlimit
    caps — never in-process.
    """
    import tempfile

    cwd = Path(tempfile.mkdtemp(prefix="skillprism_smoke_"))
    env = _minimal_env(cwd, {})
    return subprocess.run(
        [sys.executable, str(script_path.resolve())],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        preexec_fn=lambda: _set_rlimits(memory_mb, cpu_seconds, fsize_mb),
    )


def run_user_code(
    code_text: str,
    variables: Mapping[str, Any],
    output_dir: Path,
    *,
    timeout: int = 120,
    memory_mb: int = 4096,
    cpu_seconds: int = 60,
    fsize_mb: int = 64,
) -> subprocess.CompletedProcess[str]:
    """Run user-supplied Python in a sandboxed child process.

    Writes the code to ``<output_dir>/.skill_code.py`` and runs it via the
    inline wrapper. Resolved benchmark variables are exposed as globals.
    Returns the ``CompletedProcess`` (caller inspects ``returncode``/output).
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / ".skill_code.py"
    script_path.write_text(code_text, encoding="utf-8")

    env = _minimal_env(output_dir, variables)
    env["SKILLPRISM_SCRIPT"] = str(script_path)

    return subprocess.run(
        [sys.executable, "-c", _USER_CODE_WRAPPER],
        cwd=str(output_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        preexec_fn=lambda: _set_rlimits(memory_mb, cpu_seconds, fsize_mb),
    )


def run_custom_runner(
    runner_path: Path,
    input_path: Path,
    output_dir: Path,
    skill_code_path: Optional[Path] = None,
    *,
    timeout: int = 300,
    memory_mb: int = 2048,
    cpu_seconds: int = 120,
    fsize_mb: int = 128,
) -> Path:
    """Run a custom benchmark ``runner.py`` in a sandboxed child process.

    The driver calls ``runner.run(skill_code, input_path, output_dir)`` and
    writes the returned output path to ``<output_dir>/.skillprism_result``.
    Returns that path. Raises ``RuntimeError`` on non-zero exit or missing result.
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_marker = output_dir / ".skillprism_result"
    if result_marker.exists():
        result_marker.unlink()

    env = _minimal_env(
        output_dir,
        {},
        extra={
            "SKILLPRISM_RUNNER": str(runner_path.resolve()),
            "SKILLPRISM_INPUT_PATH": str(input_path),
            "SKILLPRISM_OUTPUT_DIR": str(output_dir),
            "SKILLPRISM_SKILL_CODE_PATH": str(skill_code_path) if skill_code_path else "",
        },
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", _CUSTOM_RUNNER_DRIVER],
            cwd=str(output_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=lambda: _set_rlimits(memory_mb, cpu_seconds, fsize_mb),
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Custom runner timed out after {timeout}s: {e}") from e

    if proc.returncode != 0:
        raise RuntimeError(f"Custom runner failed (exit {proc.returncode}): {proc.stderr[:1000]}")
    if not result_marker.exists():
        raise RuntimeError(
            f"Custom runner did not write result marker; stderr: {proc.stderr[:500]}"
        )
    return Path(result_marker.read_text(encoding="utf-8").strip())
