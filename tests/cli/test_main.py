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
        assert "Usage" in result.output or "Polymind" in result.output

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


class TestRunCommand:
    """Cover run command branches."""

    def test_run_with_strategy_file(self, tmp_path):
        """--strategy-file loads text from a file."""
        f = tmp_path / "strat.txt"
        f.write_text("Bands strategy with 2% margin")
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--strategy-file", str(f)])
        assert result.exit_code == 0

    def test_run_with_once_flag(self):
        """--once runs single tick."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "momentum 7d top 3", "--once"])
        assert result.exit_code == 0

    def test_run_with_dry_run(self):
        """--dry-run mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "classic MM 2% spread", "--dry-run"])
        assert result.exit_code == 0

    def test_run_with_paper(self):
        """--paper mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "AMM 5 levels", "--paper"])
        assert result.exit_code == 0

    def test_run_with_error(self):
        """Non-existent strategy still produces output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", ""])
        assert result.exit_code == 0


class TestTemplatesCommand:
    def test_templates_list(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["templates", "list"])
        assert result.exit_code == 0

    def test_templates_show(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["templates", "show", "amm_concentrated"])
        assert result.exit_code == 0
        assert "AMM" in result.output

    def test_templates_show_not_found(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["templates", "show", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_templates_run(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["templates", "run", "classic_mm_simple", "--once"])
        assert result.exit_code == 0

    def test_templates_run_not_found(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["templates", "run", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output


class TestFactorCommand:
    def test_factor_discover(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["factor", "discover", "momentum 7d top decile"])
        assert result.exit_code == 0
        assert "Factor" in result.output

    def test_factor_backtest(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["factor", "backtest", "momentum 7d top decile"])
        assert result.exit_code == 0
        assert "Factor" in result.output


class TestSetupCommand:
    def test_setup(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["setup"])
        assert result.exit_code == 0
        assert "Setup" in result.output


class TestReportCommands:
    def test_report_dashboard(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "dashboard"])
        assert result.exit_code == 0

    def test_report_positions(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "positions"])
        assert result.exit_code == 0

    def test_report_pnl(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "pnl"])
        assert result.exit_code == 0

    def test_report_risk(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "risk"])
        assert result.exit_code == 0
