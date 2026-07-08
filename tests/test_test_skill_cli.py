#!/usr/bin/env python3
"""Tests for skillprism.test_skill_cli argument handling."""

from __future__ import annotations

import os
from pathlib import Path

from skillprism.test_skill_cli import build_parser, resolve_args


def test_build_parser_help() -> None:
    parser = build_parser()
    args = parser.parse_args(["--skill", "foo", "--registry", "registry.yaml"])
    assert args.skill == "foo"
    assert args.registry == "registry.yaml"


def test_resolve_args_defaults_to_verify_only() -> None:
    parser = build_parser()
    args = parser.parse_args(["--skill", "foo", "--registry", "registry.yaml"])
    assert resolve_args(args) == 0
    assert args.verify_only is True


def test_resolve_args_run_with_agent_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["--skill", "foo", "--registry", "registry.yaml"])
    os.environ["SKILLPRISM_AGENT_COMMAND"] = "echo agent"
    try:
        assert resolve_args(args) == 0
        assert args.verify_only is False
    finally:
        del os.environ["SKILLPRISM_AGENT_COMMAND"]


def test_resolve_args_code_disables_verify_only(tmp_path: Path) -> None:
    code = tmp_path / "script.py"
    code.write_text("print('hi')", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["--skill", "foo", "--registry", "registry.yaml", "--code", str(code)])
    assert resolve_args(args) == 0
    assert args.verify_only is False


def test_resolve_args_code_missing_returns_error() -> None:
    parser = build_parser()
    args = parser.parse_args(["--skill", "foo", "--registry", "registry.yaml", "--code", "nope.py"])
    assert resolve_args(args) == 2


def test_resolve_args_verify_only_conflicts_with_code(tmp_path: Path) -> None:
    code = tmp_path / "script.py"
    code.write_text("print('hi')", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(
        ["--skill", "foo", "--registry", "registry.yaml", "--code", str(code), "--verify-only"]
    )
    assert resolve_args(args) == 2


class TestMain:
    def test_main_single_pass(self, capsys, tmp_path: Path) -> None:
        from unittest.mock import patch

        from skillprism import test_skill_cli

        with patch.object(test_skill_cli, "run_benchmarks", return_value={"_all_pass": True}):
            with patch("sys.argv", ["test-skill", "--skill", "foo", "--registry", "registry.yaml"]):
                assert test_skill_cli.main() == 0
        captured = capsys.readouterr()
        assert "PASS" in captured.out

    def test_main_single_fail(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from skillprism import test_skill_cli

        with patch.object(test_skill_cli, "run_benchmarks", return_value={"_all_pass": False}):
            with patch("sys.argv", ["test-skill", "--skill", "foo", "--registry", "registry.yaml"]):
                assert test_skill_cli.main() == 1

    def test_main_gradual(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from skillprism import test_skill_cli

        with patch.object(test_skill_cli, "run_gradual_pipeline", return_value={"_all_pass": True}):
            with patch(
                "sys.argv",
                [
                    "test-skill",
                    "--skill",
                    "foo",
                    "--registry",
                    "registry.yaml",
                    "--mode",
                    "gradual",
                ],
            ):
                assert test_skill_cli.main() == 0

    def test_main_gradual_level_rejected(self, capsys, tmp_path: Path) -> None:
        from unittest.mock import patch

        from skillprism import test_skill_cli

        with patch.object(test_skill_cli, "run_gradual_pipeline", return_value={"_all_pass": True}):
            with patch(
                "sys.argv",
                [
                    "test-skill",
                    "--skill",
                    "foo",
                    "--registry",
                    "registry.yaml",
                    "--mode",
                    "gradual",
                    "--level",
                    "1",
                ],
            ):
                assert test_skill_cli.main() == 2
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_main_quick_pass(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from skillprism import test_skill_cli

        with patch.object(test_skill_cli, "run_benchmarks", return_value={"_all_pass": True}):
            with patch(
                "sys.argv",
                [
                    "test-skill",
                    "--skill",
                    "foo",
                    "--registry",
                    "registry.yaml",
                    "--mode",
                    "quick",
                ],
            ):
                assert test_skill_cli.main() == 0

    def test_main_quick_level0_fail(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from skillprism import test_skill_cli

        with patch.object(test_skill_cli, "run_benchmarks", return_value={"_all_pass": False}):
            with patch(
                "sys.argv",
                [
                    "test-skill",
                    "--skill",
                    "foo",
                    "--registry",
                    "registry.yaml",
                    "--mode",
                    "quick",
                ],
            ):
                assert test_skill_cli.main() == 1

    def test_main_with_code(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from skillprism import test_skill_cli

        code = tmp_path / "code.py"
        code.write_text("print('hi')", encoding="utf-8")
        with patch.object(test_skill_cli, "run_benchmarks", return_value={"_all_pass": True}):
            with patch(
                "sys.argv",
                [
                    "test-skill",
                    "--skill",
                    "foo",
                    "--registry",
                    "registry.yaml",
                    "--code",
                    str(code),
                ],
            ):
                assert test_skill_cli.main() == 0
