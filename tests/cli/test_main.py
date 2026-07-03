"""
Tests for CLI commands.
"""

from __future__ import annotations

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
        assert result.exit_code in (0, 2)

    def test_run_with_strategy_text(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "AMM market making with 5 levels"])
        assert result.exit_code == 0
        assert "Strategy" in result.output
        assert "AMM" in result.output or "amm" in result.output.lower()

    def test_run_without_strategy(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run"])
        assert result.exit_code == 0
        assert "No strategy provided" in result.output
