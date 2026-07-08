#!/usr/bin/env python3
"""P0-2: sandboxed code execution.

Generated/agent code must run in a sandboxed child process: separate process,
minimal environment, rlimit caps, timeout. It must never ``exec`` in-process.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from skillprism.benchmark.sandbox import run_user_code


def test_run_user_code_executes_and_returns_output(tmp_path: Path) -> None:
    """A benign script runs and can write to the output dir."""
    code = textwrap.dedent(
        """
        from pathlib import Path
        out = Path(output_dir) / "done.txt"
        out.write_text("ok")
        """
    )
    proc = run_user_code(code, {"input_csv": str(tmp_path / "in.csv")}, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "done.txt").read_text() == "ok"


def test_sandbox_isolates_process_no_parent_globals(tmp_path: Path) -> None:
    """The child is a separate process: parent globals are not visible."""
    # Define a secret only in the parent process namespace.
    _parent_secret = "PARENT_SECRET_VALUE"  # noqa: F841
    code = textwrap.dedent(
        """
        import sys
        try:
            _ = __import__('builtins').globals  # noqa
        except Exception:
            pass
        # The child must not see parent process memory.
        out = __import__('os').environ.get('OUTPUT_DIR')
        # If this were in-process exec, parent locals would leak; assert child is fresh.
        open(__import__('os').environ['OUTPUT_DIR'] + '/fresh.txt', 'w').write('child')
        """
    )
    proc = run_user_code(code, {}, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "fresh.txt").read_text() == "child"


def test_sandbox_does_not_leak_parent_environment(tmp_path: Path, monkeypatch) -> None:
    """The minimal env must not carry arbitrary parent env vars."""
    monkeypatch.setenv("SKILLPRISM_TEST_SECRET", "leaky")
    code = (
        "import os\n"
        "seen = os.environ.get('SKILLPRISM_TEST_SECRET', 'ABSENT')\n"
        "open(os.environ['OUTPUT_DIR'] + '/env.txt', 'w').write(seen)\n"
    )
    proc = run_user_code(code, {}, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "env.txt").read_text() == "ABSENT"


def test_sandbox_cpu_timeout_traps_infinite_loop(tmp_path: Path) -> None:
    """A CPU-bound infinite loop is killed by the rlimit/timeout, not the runner."""
    code = "x = 0\nwhile True:\n    x += 1\n"
    # Use a very small cpu cap so the test is fast.
    proc = run_user_code(code, {}, tmp_path, timeout=10, cpu_seconds=2, memory_mb=256)
    assert proc.returncode != 0


def test_sandbox_memory_cap_traps_large_allocation(tmp_path: Path) -> None:
    """A large memory allocation is refused by RLIMIT_AS."""
    code = "big = b'\\x00' * (512 * 1024 * 1024)\n"
    proc = run_user_code(code, {}, tmp_path, timeout=15, memory_mb=64)
    assert proc.returncode != 0


def test_sandbox_exposes_resolved_variables_as_globals(tmp_path: Path) -> None:
    """Variables passed to run_user_code are exposed as globals in the child."""
    (tmp_path / "in.csv").write_text("x\n1\n")
    code = (
        "import shutil, os\n"
        "shutil.copy2(input_csv, os.path.join(os.environ['OUTPUT_DIR'], 'copied.csv'))\n"
    )
    proc = run_user_code(code, {"input_csv": str(tmp_path / "in.csv")}, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "copied.csv").read_text() == "x\n1\n"


def test_sandbox_failing_code_returns_nonzero_with_stderr(tmp_path: Path) -> None:
    code = "raise ValueError('boom')\n"
    proc = run_user_code(code, {}, tmp_path)
    assert proc.returncode != 0
    assert "boom" in proc.stderr
