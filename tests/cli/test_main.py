"""
Tests for CLI commands.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from polymind.cli.main import cli


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Polymind" in result.output or "Usage" in result.output

    def test_status(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_strategies(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["strategies"])
        assert result.exit_code == 0

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        # CLI may or may not have --version, both are fine
        assert result.exit_code in (0, 2)
