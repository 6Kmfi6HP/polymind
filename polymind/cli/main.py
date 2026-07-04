"""
Polymind CLI — run market-making strategies from the terminal.

Usage:
    polymind run "Describe your strategy in English"
    polymind run --strategy amm --market <condition-id>
    polymind strategies
    polymind status
"""

import click
from rich.console import Console
from rich.table import Table

from polymind.core.config import load_config

console = Console()

BANNER = """
[bold blue]╔══════════════════════════════════════════════╗[/bold blue]
[bold blue]║[/bold blue]        [bold white]🧠 Polymind v0.1.0[/bold white]              [bold blue]║[/bold blue]
[bold blue]║[/bold blue]   [dim]AI-native market making[/dim]               [bold blue]║[/bold blue]
[bold blue]╚══════════════════════════════════════════════╝[/bold blue]
"""


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="0.1.0", prog_name="polymind")
def cli(ctx):
    """
    Polymind — AI-native market making for Polymarket.

    Write market-making strategies in natural language.
    Let AI assemble, tune, and execute them.
    """
    ctx.ensure_object(dict)
    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        console.print()
        console.print("[bold]Usage:[/bold]")
        console.print('  [green]polymind run "your strategy"[/green]    Run a strategy')
        console.print("  [green]polymind strategies[/green]              List strategies")
        console.print("  [green]polymind status[/green]                  Check configuration")
        console.print("  [green]polymind setup[/green]                   Configure API keys")
        console.print()


@cli.command()
@click.argument("strategy_text", required=False)
@click.option("--strategy-file", "-s", type=click.Path(exists=True))
@click.option("--paper", is_flag=True, help="Paper trading mode")
@click.option("--dry-run", is_flag=True, help="Simulation mode (no real trades)")
@click.option("--once", is_flag=True, help="Run once and exit")
@click.option("--interval", "-i", type=int, default=60, help="Loop interval in seconds")
@click.pass_context
def run(ctx, strategy_text, strategy_file, paper, dry_run, once, interval):
    """
    Run a market-making strategy.

    STRATEGY_TEXT is a natural-language description of your strategy.
    Or use --strategy-file to load from a text file.

    Examples:

        polymind run "AMM market making, 200 USDC, depth 0.1"

        polymind run --strategy amm --paper

        polymind run -s my_strategy.txt --live
    """
    try:
        console.print(BANNER)

        # Determine strategy text
        if strategy_file:
            with open(strategy_file) as f:
                strategy_text = f.read()
        elif not strategy_text:
            console.print(
                "[yellow]No strategy provided. Use inline text or --strategy-file.[/yellow]"
            )
            return

        # Show what we're running
        mode = (
            "[yellow]DRY RUN[/yellow]"
            if dry_run
            else "[cyan]PAPER[/cyan]"
            if paper
            else "[red]LIVE[/red]"
        )
        console.print(f"  Strategy: {strategy_text[:60]}...")
        console.print(f"  Mode:     {mode}")
        console.print(f"  Interval: {interval}s")
        console.print()

        # Wire up strategy execution
        strategy_text = strategy_text or ""
        from polymind.studio.generator import StrategyGenerator

        gen = StrategyGenerator()
        config = gen.generate(strategy_text)
        console.print(f"  Strategy: [bold]{config.strategy_name}[/bold] ({config.template.name})")
        console.print(f"  Confidence: {config.confidence:.0%}")
        console.print()

        if config.params:
            console.print("[bold]Parameters:[/bold]")
            for key, val in config.params.items():
                console.print(f"  {key}: {val}")

        # Build executor
        if dry_run or once:
            from polymind.execution.executor import PaperExecutor
            from polymind.execution.fill_model import FillModel, FillModelConfig

            fill_model = FillModel(FillModelConfig())
            executor = PaperExecutor(fill_model=fill_model)
            console.print("[dim]Dry-run mode — simulated fills, no orders placed.[/dim]")
        elif paper:
            from polymind.execution.executor import PaperExecutor
            from polymind.execution.fill_model import FillModel, FillModelConfig

            fill_model = FillModel(FillModelConfig())
            executor = PaperExecutor(fill_model=fill_model)
            console.print("[cyan]PAPER[/cyan] executor ready — simulated fills.")
        else:
            from polymind.polymarket.client import PolymarketClient

            client = PolymarketClient()
            _run_async(client.connect())
            from polymind.execution.live_executor import LiveExecutor

            executor = LiveExecutor(client=client)
            console.print("[red]LIVE[/red] executor ready — real CLOB orders.")

        # Set up strategy instance
        from polymind.strategies import get_strategy

        strategy_instance = get_strategy(config.strategy_name, config)

        # Build TradingEngine
        from polymind.core.engine import TradingEngine, TradingEngineConfig

        engine = TradingEngine(
            strategy=strategy_instance,
            executor=executor,
            config=TradingEngineConfig(
                strategy_name=config.strategy_name,
                loop_interval=interval,
                dry_run=dry_run or False,
            ),
        )

        console.print("[green]✓[/green] TradingEngine ready — observe → decide → act.")
        console.print()

        if once:
            # Single tick
            from datetime import datetime, timezone

            from polymind.execution.fill_model import MarketSnapshot

            dummy = MarketSnapshot(
                market_id="",
                timestamp=datetime.now(timezone.utc),
                bid_price=0.0,
                ask_price=0.0,
                mid_price=0.0,
                bid_size=0.0,
                ask_size=0.0,
            )
            result = _run_async(engine.run_tick(dummy))
            console.print(f"[dim]Result: {result.orders_placed} orders placed.[/dim]")
        else:
            console.print("[green]✓[/green] Engine configured for continuous operation.")
            console.print(f"[dim]  Strategy: {config.strategy_name}, interval={interval}s[/dim]")
            console.print(
                "[dim]  Use --once for single-tick execution, or integrate with async market provider.[/dim]"
            )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command(name="strategies")
def list_strategies():
    """List all available market-making strategies."""
    from polymind.core.discover import discover_strategies
    from polymind.strategies import list_strategies as get_strategies

    builtin = get_strategies()
    discovered_raw = discover_strategies()

    # Discovered plugins not already known as built-in
    discovered: dict[str, str] = {}
    for name, cls in discovered_raw.items():
        if name not in builtin:
            discovered[name] = cls.__doc__ or ""

    console.print("\n[bold]Available Strategies[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Strategy", style="cyan", width=16)
    table.add_column("Description", width=60)
    table.add_column("Source")

    for name, desc in builtin.items():
        table.add_row(name, desc, "[green]built-in[/green]")

    for name, desc in discovered.items():
        table.add_row(name, desc, "[yellow]plugin[/yellow]")

    console.print(table)
    console.print()
    console.print('[dim]Use [bold]polymind run "<strategy description>"[/bold] to execute.[/dim]')
    console.print()


@cli.command()
def status():
    """Check configuration and system status."""

    config = load_config()
    console.print(BANNER)
    console.print("\n[bold]Configuration[/bold]\n")

    agents = config.get_available_agents()
    if agents:
        console.print(f"[green]✓[/green] AI Providers: {', '.join(agents)}")
    else:
        console.print("[yellow]○[/yellow] No AI providers configured")

    if config.has_wallet():
        console.print(f"[green]✓[/green] Wallet: Connected ({config.platform})")
    else:
        console.print("[yellow]○[/yellow] Wallet: Not connected (read-only)")

    mode = "Safe (dry-run)" if config.dry_run else "[red]Live[/red]"
    console.print(f"[{'yellow' if config.dry_run else 'red'}]○[/] Mode: {mode}")

    executor_type = (
        "[cyan]PaperExecutor[/cyan] (sandbox)"
        if config.dry_run
        else "[red]LiveExecutor[/red] (CLOB)"
    )
    console.print(f"[green]✓[/green] Executor: {executor_type}")
    console.print()
    console.print(
        "[dim]Run [bold]polymind setup[/bold] to configure API keys or create a .env file.[/dim]"
    )
    console.print()


@cli.command()
def setup():
    """Interactive setup wizard."""
    console.print(BANNER)
    console.print("\n[bold]Setup Wizard[/bold] — coming in v0.2")
    console.print()
    console.print("For now, create a [bold].env[/bold] file with:")

    env_template = """
    # AI Provider (at least one required)
    ANTHROPIC_API_KEY=sk-ant-...
    OPENAI_API_KEY=sk-...
    GOOGLE_API_KEY=...

    # Wallet (optional for paper/dry-run)
    PRIVATE_KEY=0x...
    """
    from rich.panel import Panel

    console.print(Panel(env_template.strip(), border_style="dim"))


def _run_async(coro):
    """Run an async coroutine synchronously in a new event loop."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@cli.group()
def report():
    """Generate operator reports."""
    pass


@report.command()
def dashboard():
    """Show combined operator dashboard."""
    try:
        from polymind.reports.dashboard import display_dashboard, generate_dashboard
        from polymind.risk.limits import LimitsConfig, LimitsManager
        from polymind.risk.manager import RiskManager
        from polymind.storage.database import DatabaseConfig
        from polymind.storage.ledger import LedgerStore

        config = load_config()
        ledger = LedgerStore(DatabaseConfig(path=getattr(config, "db_path", ":memory:")))
        risk_mgr = RiskManager()
        limits_mgr = LimitsManager(
            LimitsConfig(positions=[], order_rate=None, daily_loss=None, exposure=None)
        )

        tables = _run_async(generate_dashboard(ledger, risk_mgr, limits_mgr))
        display_dashboard(tables)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@report.command()
def positions():
    """Show position summary."""
    try:
        config = load_config()
        from polymind.reports.positions import format_positions_table, get_position_report
        from polymind.storage.database import DatabaseConfig
        from polymind.storage.ledger import LedgerStore

        ledger = LedgerStore(DatabaseConfig(path=getattr(config, "db_path", ":memory:")))
        positions = _run_async(get_position_report(ledger))
        console.print(format_positions_table(positions))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@report.command()
def pnl():
    """Show P&L summary."""
    try:
        config = load_config()
        from polymind.reports.pnl import format_pnl_table, get_pnl_report
        from polymind.storage.database import DatabaseConfig
        from polymind.storage.ledger import LedgerStore

        ledger = LedgerStore(DatabaseConfig(path=getattr(config, "db_path", ":memory:")))
        report = _run_async(get_pnl_report(ledger))
        cash = _run_async(ledger.get_cash_balance())
        console.print(format_pnl_table(report, cash))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@report.command()
def risk():
    """Show risk status."""
    try:
        from polymind.reports.risk import format_risk_table, get_risk_report
        from polymind.risk.limits import LimitsConfig, LimitsManager
        from polymind.risk.manager import RiskManager

        risk_mgr = RiskManager()
        limits_mgr = LimitsManager(
            LimitsConfig(positions=[], order_rate=None, daily_loss=None, exposure=None)
        )
        report = get_risk_report(risk_mgr, limits_mgr)
        console.print(format_risk_table(report))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def main():
    """Entry point."""
    from polymind.factors.registry import register_builtin_factors
    from polymind.strategies import register_builtin_strategies

    # Register built-in plugins on startup
    register_builtin_strategies()
    register_builtin_factors()

    cli()


if __name__ == "__main__":
    main()
