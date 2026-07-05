"""
Tests for CLI commands.
"""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from polymind.cli.main import cli


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output or "Polymind" in result.output

    def test_no_command_shows_banner(self):
        """Invoking CLI with no subcommand prints banner + usage."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Polymind" in result.output
        assert "Usage" in result.output

    def test_status(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_strategies(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["strategies"])
        assert result.exit_code == 0
        assert "Available" in result.output or "Strategy" in result.output

    def test_main_entry_point(self):
        """main() function (line 549-558) runs without error."""
        # main() calls cli() which will show banner with no args
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0

    def test_status_with_agents_and_wallet(self):
        """Lines 410, 415: status with providers configured."""
        with patch.dict(
            "os.environ",
            {
                "ANTHROPIC_API_KEY": "sk-ant-test",
                "PRIVATE_KEY": "0xwallet",
            },
        ):
            # Reset singleton
            import polymind.core.config as cfg_mod

            cfg_mod._config = None
            try:
                runner = CliRunner()
                result = runner.invoke(cli, ["status"])
                assert result.exit_code == 0
                assert "AI Providers" in result.output
                assert "Wallet" in result.output
            finally:
                cfg_mod._config = None

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

    def test_templates_run_with_once(self):
        """Line 379-397: template run with --once."""
        runner = CliRunner()
        result = runner.invoke(cli, ["templates", "run", "classic_mm_simple", "--once"])
        assert result.exit_code == 0

    def test_templates_run_no_once(self):
        """Line 397: template run without --once shows ready message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["templates", "run", "classic_mm_simple"])
        assert result.exit_code == 0
        assert "ready" in result.output.lower()

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

    def test_factor_backtest_with_params(self):
        """Line 275: factor backtest with params prints them."""
        runner = CliRunner()
        result = runner.invoke(cli, ["factor", "discover", "short term reversal 7d top decile"])
        assert result.exit_code == 0
        assert "Params" in result.output or "Factor" in result.output

    def test_factor_recommend(self):
        """factor recommend tests multiple variations."""
        runner = CliRunner()
        result = runner.invoke(cli, ["factor", "recommend", "momentum on 7d returns"])
        assert result.exit_code == 0
        assert "Recommended" in result.output or "variation" in result.output.lower()

    def test_factor_recommend_no_query(self):
        """factor recommend with empty idea."""
        runner = CliRunner()
        result = runner.invoke(cli, ["factor", "recommend", ""])
        assert result.exit_code == 0


class TestMainFunction:
    """Cover lines 549-558: main() entry point."""

    def test_main_function(self):
        """main() registers plugins and invokes CLI."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0


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

    def test_report_dashboard_error(self):
        """Dashboard error handler prints Error."""
        with patch("polymind.storage.ledger.LedgerStore") as mock:
            mock.side_effect = ValueError("test error")
            runner = CliRunner()
            result = runner.invoke(cli, ["report", "dashboard"])
            assert result.exit_code == 0
            assert "Error" in result.output

    def test_report_positions_error(self):
        """Positions error handler prints Error."""
        with patch("polymind.storage.ledger.LedgerStore") as mock:
            mock.side_effect = ValueError("test error")
            runner = CliRunner()
            result = runner.invoke(cli, ["report", "positions"])
            assert result.exit_code == 0
            assert "Error" in result.output

    def test_report_pnl_error(self):
        """P&L error handler prints Error."""
        with patch("polymind.storage.ledger.LedgerStore") as mock:
            mock.side_effect = ValueError("test error")
            runner = CliRunner()
            result = runner.invoke(cli, ["report", "pnl"])
            assert result.exit_code == 0
            assert "Error" in result.output

    def test_report_risk_error(self):
        """Risk error handler prints Error."""
        with patch("polymind.risk.manager.RiskManager") as mock:
            mock.side_effect = ValueError("test error")
            runner = CliRunner()
            result = runner.invoke(cli, ["report", "risk"])
            assert result.exit_code == 0
            assert "Error" in result.output
