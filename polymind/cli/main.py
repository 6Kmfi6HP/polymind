"""
Polymind CLI — run market-making strategies from the terminal.

Usage:
    polymind run "Describe your strategy in English"
    polymind run --strategy amm --market <condition-id>
    polymind strategies
    polymind status
"""

import asyncio
import sys

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
        console.print("  [green]polymind run \"your strategy\"[/green]    Run a strategy")
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
def run(strategy_text, strategy_file, paper, dry_run, once, interval):
    """
    Run a market-making strategy.

    STRATEGY_TEXT is a natural-language description of your strategy.
    Or use --strategy-file to load from a text file.

    Examples:

        polymind run "AMM market making, 200 USDC, depth 0.1"

        polymind run --strategy amm --paper

        polymind run -s my_strategy.txt --live
    """
    console.print(BANNER)

    # Determine strategy text
    if strategy_file:
        with open(strategy_file) as f:
            strategy_text = f.read()
    elif not strategy_text:
        console.print("[yellow]No strategy provided. Use inline text or --strategy-file.[/yellow]")
        return

    # Show what we're running
    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[cyan]PAPER[/cyan]" if paper else "[red]LIVE[/red]"
    console.print(f"  Strategy: {strategy_text[:60]}...")
    console.print(f"  Mode:     {mode}")
    console.print(f"  Interval: {interval}s")
    console.print()

    # TODO: Wire up actual strategy execution
    console.print("[dim]Strategy execution coming in v0.2 — this is a skeleton release.[/dim]")
    console.print("[dim]Check back soon for working strategy backends![/dim]")
    console.print()


@cli.command(name="strategies")
def list_strategies():
    """List all available market-making strategies."""
    from polymind.strategies import list_strategies as get_strategies

    strategies = {
        "amm": "Concentrated liquidity AMM simulation (CPMM order ladders)",
        "bands": "Price margin bands around midpoint",
        "maker-rebate": "Y+N<$1 arbitrage + maker fee rebate",
        "event-mm": "WebSocket-driven real-time MM with stop-loss",
        "sniper": "Deep discount GTC orders on short-term options",
        "copy-trade": "Mirror target wallet trades in real-time",
        "classic-mm": "Split USDC → limit sell at profit target",
    }

    console.print("\n[bold]Available Strategies[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Strategy", style="cyan", width=16)
    table.add_column("Description", width=60)
    table.add_column("Status")

    for name, desc in strategies.items():
        table.add_row(name, desc, "[yellow]coming soon[/yellow]")

    console.print(table)
    console.print()
    console.print("[dim]Strategies are being ported from the source projects.[/dim]")
    console.print()


@cli.command()
def status():
    """Check configuration and system status."""
    from polymind.core.config import get_config

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
    console.print()
    console.print("[dim]Run [bold]polymind setup[/bold] to configure API keys.[/dim]")
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


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
