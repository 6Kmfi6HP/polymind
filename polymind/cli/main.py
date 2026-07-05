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
@click.version_option(version="0.7.0", prog_name="polymind")
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
    console.print(
        "[dim]Use [bold]polymind templates[/bold] to see ready-to-deploy templates.[/dim]"
    )
    console.print()


@cli.group()
def templates():
    """List and deploy pre-configured strategy templates."""
    pass


@cli.group()
def factor():
    """AI-powered factor discovery and backtesting."""
    pass


@factor.command(name="discover")
@click.argument("description")
def factor_discover(description: str):
    """Discover a factor from a natural language description."""
    from polymind.studio.factor_discovery import FactorDiscoveryAgent

    agent = FactorDiscoveryAgent()
    fd = _run_async(agent.discover(description))

    console.print("\n[bold]Factor Discovery Result[/bold]")
    console.print(f"  Name:      [green]{fd.name}[/green]")
    console.print(f"  Lookback:  {fd.lookback}")
    console.print(f"  Scoring:   {fd.scoring_fn}")
    console.print(f"  Top N:     {fd.top_n}")
    console.print(f"  Rebalance: every {fd.rebal_freq_hours}h")
    if fd.params:
        console.print(f"  Params:    {fd.params}")
    console.print()


@factor.command(name="backtest")
@click.argument("description")
def factor_backtest(description: str):
    """Discover and backtest a factor from a description."""
    from polymind.studio.factor_discovery import FactorDiscoveryAgent

    agent = FactorDiscoveryAgent()
    card = _run_async(agent.discover_and_backtest(description))

    console.print("\n[bold]Factor Backtest Result[/bold]")
    status = "[green]✅ APPROVED[/green]" if card.approved else "[red]❌ REJECTED[/red]"
    console.print(f"  Name:      [green]{card.definition.name}[/green]")
    console.print(f"  Status:    {status}")
    console.print()
    console.print("[bold]Performance:[/bold]")
    console.print(f"  Sharpe:    {card.sharpe:.2f}")
    console.print(f"  Sortino:   {card.sortino:.2f}")
    console.print(f"  Max DD:    {card.max_drawdown:.1%}")
    console.print(f"  Return:    {card.total_return:.1%}")
    console.print(f"  Win Rate:  {card.win_rate:.1%}")
    console.print(f"  Trades:    {card.total_trades}")
    if card.error:
        console.print(f"  Error:     [red]{card.error}[/red]")
    console.print()
    if card.ic_rank:
        console.print("[bold]Information Coefficient:[/bold]")
        console.print(f"  IC Rank:   {card.ic_rank:.4f}")
        console.print(f"  IC IR:     {card.ic_ir:.2f}")
        console.print(f"  Hit Rate:  {card.ic_hit_rate:.0%}")
        if card.ic_decile_1:
            console.print(f"  Decile 1:  {card.ic_decile_1:.4f}  (highest-score portfolio)")
        if card.ic_decile_10:
            console.print(f"  Decile 10: {card.ic_decile_10:.4f}  (lowest-score portfolio)")
        if card.decay_half_life:
            console.print(f"  Half-Life: {card.decay_half_life:.1f} periods")
        console.print()
    if card.wf_sharpe_mean:
        console.print("[bold]Walk-Forward:[/bold]")
        console.print(f"  Sharpe μ:  {card.wf_sharpe_mean:.2f}")
        console.print(f"  Sharpe σ:  {card.wf_sharpe_std:.2f}")
        console.print(f"  Consist.:  {card.wf_sharpe_consistency:.0%}")
        console.print(f"  Avg DD:    {card.wf_avg_drawdown:.1%}")
        console.print()
    console.print()


@cli.command()
@click.option("--interval", "-i", type=int, default=300, help="Loop interval in seconds")
@click.option("--strategy", "-s", default="auto", help="Strategy name or 'auto'")
@click.option("--log-file", type=click.Path(), default="polymind-daemon.log")
@click.option("--paper", is_flag=True, help="Paper trading mode")
def daemon(interval: int, strategy: str, log_file: str, paper: bool):
    """Run polymind as a continuous background daemon.

    Sets up a TradingEngine with the specified strategy and runs it
    on a configurable interval.  Logs tick results to a file.
    Use Ctrl+C to stop gracefully.
    """
    import asyncio
    import logging
    import signal

    from polymind.core.engine import TradingEngine, TradingEngineConfig
    from polymind.execution.executor import PaperExecutor
    from polymind.execution.fill_model import FillModel, FillModelConfig
    from polymind.studio.generator import StrategyGenerator

    # Set up file logging
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger("polymind.daemon")

    console.print(BANNER)
    console.print()
    console.print("[bold]Daemon Mode[/bold]")
    console.print(f"  Interval:  {interval}s")
    console.print(f"  Strategy:  {strategy}")
    console.print(f"  Log file:  {log_file}")
    console.print(f"  Mode:      {'[cyan]PAPER[/cyan]' if paper else '[yellow]DRY RUN[/yellow]'}")
    console.print()

    # Resolve strategy
    if strategy == "auto":
        gen = StrategyGenerator()
        config = gen.generate("Basic market making with 2% spread")
        strategy_name = config.strategy_name
        from polymind.strategies import get_strategy as resolve_strategy

        strategy_instance = resolve_strategy(config.strategy_name, config)
        logger.info("Auto-generated strategy: %s", strategy_name)
    else:
        from polymind.core.strategy import StrategyConfig
        from polymind.strategies import get_strategy as resolve_strategy

        cfg = StrategyConfig(name=strategy)
        strategy_instance = resolve_strategy(strategy, cfg)
        strategy_name = strategy
        logger.info("Using strategy: %s", strategy)

    fill_model = FillModel(FillModelConfig())
    executor = PaperExecutor(fill_model=fill_model)

    engine = TradingEngine(
        strategy=strategy_instance,
        executor=executor,
        config=TradingEngineConfig(
            strategy_name=strategy_name,
            loop_interval=interval,
            dry_run=True,
        ),
    )

    console.print("[green]✓[/green] Daemon initialised. Starting loop...")
    console.print("[dim]Press Ctrl+C to stop gracefully.[/dim]")
    console.print()

    stop_event = asyncio.Event()

    def _handle_signal(*_: object) -> None:
        console.print("\n[yellow]Shutdown signal received, stopping...[/yellow]")
        stop_event.set()

    async def _daemon_loop() -> None:
        """Run the daemon loop until stopped."""
        import asyncio as _asyncio
        from datetime import datetime as _datetime
        from datetime import timezone as _timezone

        from polymind.execution.fill_model import MarketSnapshot

        tick_count = 0
        while not stop_event.is_set():
            tick_count += 1
            ts = _datetime.now(_timezone.utc)
            dummy = MarketSnapshot(
                market_id="",
                timestamp=ts,
                bid_price=0.0,
                ask_price=0.0,
                mid_price=0.0,
                bid_size=0.0,
                ask_size=0.0,
            )
            try:
                result = await engine.run_tick(dummy)
                logger.info(
                    "Tick %d: %d orders placed, %d errors",
                    tick_count,
                    result.orders_placed,
                    getattr(result, "errors", 0),
                )
            except Exception as exc:
                logger.error("Tick %d failed: %s", tick_count, exc)
            try:
                await _asyncio.wait_for(stop_event.wait(), timeout=float(interval))
                break
            except _asyncio.TimeoutError:
                pass

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except (NotImplementedError, ValueError):
            signal.signal(sig, lambda *_: None)

    try:
        loop.run_until_complete(_daemon_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
    finally:
        loop.close()
        console.print("[green]Daemon stopped.[/green]")
    console.print()


@factor.command(name="recommend")
@click.argument("idea")
def factor_recommend(idea: str):
    """Discover, compare variations, and recommend the best factor.

    IDEA is a natural language description of the factor idea.
    The agent tests multiple lookback/top_n variations and reports
    the configuration with the highest Sharpe ratio.
    """
    from polymind.studio.factor_discovery import FactorDiscoveryAgent

    agent = FactorDiscoveryAgent()

    # Generate variations to test
    variations = [
        f"{idea}, top 5, 7d lookback",
        f"{idea}, top 10, 7d lookback",
        f"{idea}, top 5, 14d lookback",
        f"{idea}, top 10, 14d lookback",
        f"{idea}, top 5, 30d lookback",
        f"{idea}, top 10, 30d lookback",
    ]

    console.print("\n[bold]Factor Recommendation Engine[/bold]")
    console.print(f"  Idea: {idea}")
    console.print(f"  Testing {len(variations)} variations...")
    console.print()

    best_card = None
    best_sharpe = -float("inf")
    results: list[tuple[str, float, str]] = []

    for i, desc in enumerate(variations):
        console.print(f"  [{i + 1}/{len(variations)}] {desc[:50]}...", end=" ")
        try:
            card = _run_async(agent.discover_and_backtest(desc))
            sharpe = card.sharpe
            status = "[green]✓[/green]" if card.approved else "[yellow]○[/yellow]"
            results.append((desc, sharpe, card.definition.name))
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_card = card
            console.print(f"{status} Sharpe={sharpe:.2f}")
        except Exception as e:
            console.print(f"[red]✗ {e}[/red]")

    if best_card:
        console.print()
        console.print("[bold green]🏆 Recommended Factor[/bold green]")
        console.print(f"  Name:      [green]{best_card.definition.name}[/green]")
        console.print(f"  Lookback:  {best_card.definition.lookback}")
        console.print(f"  Top N:     {best_card.definition.top_n}")
        console.print(f"  Sharpe:    {best_card.sharpe:.2f}")
        console.print(f"  Sortino:   {best_card.sortino:.2f}")
        console.print(f"  Max DD:    {best_card.max_drawdown:.1%}")
        console.print(f"  Return:    {best_card.total_return:.1%}")
        console.print(
            f"  Approved:  {'[green]YES[/green]' if best_card.approved else '[red]NO[/red]'}"
        )
        if best_card.ic_rank:
            console.print(f"  IC Rank:   {best_card.ic_rank:.4f}")
        console.print()
    else:
        console.print("[red]No viable factor found.[/red]")
    console.print()


@templates.command(name="list")
def list_templates():
    """Show all available strategy templates."""
    from rich.table import Table

    from polymind.templates import TemplateLibrary

    lib = TemplateLibrary()
    all_templates = lib.list_templates()

    console.print("\n[bold]Available Strategy Templates[/bold]\n")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Template", style="cyan", width=22)
    table.add_column("Description", width=55)
    table.add_column("Type", width=14)
    table.add_column("Tags")

    for t in all_templates:
        tags_str = ", ".join(t.tags[:3])
        table.add_row(t.name, t.description, t.strategy_type, tags_str)

    console.print(table)
    console.print()
    console.print("[dim]Use [bold]polymind template show <name>[/bold] for details.[/dim]")
    console.print()


@templates.command(name="show")
@click.argument("name")
def show_template(name: str):
    """Show details for a specific template."""
    from polymind.templates import TemplateLibrary

    lib = TemplateLibrary()
    info = lib.get_template(name)
    if info is None:
        console.print(f"[red]Template '{name}' not found.[/red]")
        return

    console.print(f"\n[bold]{info.name}[/bold]")
    console.print(f"  [dim]{info.description}[/dim]")
    console.print(f"  Type: [green]{info.strategy_type}[/green]")
    console.print()
    console.print("[bold]Parameters:[/bold]")
    for key, val in info.params.items():
        console.print(f"  {key}: {val}")
    console.print()
    console.print("[bold]Risk Limits:[/bold]")
    for key, val in info.risk_limits.items():
        console.print(f"  {key}: {val}")
    console.print()
    console.print(f"Tags: {', '.join(info.tags)}")
    console.print()


@templates.command(name="run")
@click.argument("name")
@click.option("--paper", is_flag=True, help="Paper trading mode")
@click.option("--once", is_flag=True, help="Run once and exit")
def run_template(name: str, paper: bool, once: bool):
    """Deploy a pre-configured strategy template."""
    from polymind.templates import TemplateLibrary

    lib = TemplateLibrary()
    info = lib.get_template(name)
    if info is None:
        console.print(f"[red]Template '{name}' not found.[/red]")
        return

    console.print(f"[green]Deploying template:[/green] {info.name}")
    console.print(f"  {info.description}")
    console.print(f"  Type: {info.strategy_type}")
    console.print()

    from polymind.core.strategy import StrategyConfig
    from polymind.strategies import get_strategy

    cfg = StrategyConfig(
        name=info.name,
        params=info.params,
    )
    strategy = get_strategy(info.strategy_type, cfg)

    from polymind.execution.executor import PaperExecutor
    from polymind.execution.fill_model import FillModel, FillModelConfig

    fill_model = FillModel(FillModelConfig())
    executor = PaperExecutor(fill_model=fill_model, initial_cash=1000.0)

    from polymind.core.engine import TradingEngine, TradingEngineConfig

    engine = TradingEngine(
        strategy=strategy,
        executor=executor,
        config=TradingEngineConfig(
            strategy_name=info.name,
            dry_run=not paper,
        ),
    )

    if once:
        console.print("[dim]Running single tick...[/dim]")
        from datetime import datetime

        from polymind.execution.fill_model import MarketSnapshot

        dummy = MarketSnapshot(
            market_id="",
            timestamp=datetime.now(),
            bid_price=0.0,
            ask_price=0.0,
            mid_price=0.0,
            bid_size=0.0,
            ask_size=0.0,
        )
        result = _run_async(engine.run_tick(dummy))
        console.print(f"[dim]Orders proposed: {result.orders_proposed}[/dim]")
    else:
        console.print(f"[green]✓[/green] {info.name} engine ready. Use --once for single tick.")


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
def plugin():
    """Manage polymind plugins (strategies, factors, workflows)."""
    pass


@plugin.command(name="list")
def plugin_list():
    """List all installed plugins grouped by type."""
    from rich.table import Table

    from polymind.core.discover import discover_all

    all_plugins = discover_all()

    console.print("\n[bold]Installed Plugins[/bold]\n")

    for kind, items in all_plugins.items():
        if not items:
            continue
        table = Table(show_header=True, header_style="bold")
        table.add_column("Name", style="cyan", width=24)
        table.add_column("Type", width=16)
        table.add_column("Module", width=40)
        for name, cls in items.items():
            table.add_row(
                name,
                kind.rstrip("s").capitalize(),
                f"{cls.__module__}.{cls.__qualname__}",
            )
        console.print(table)
        console.print()

    total = sum(len(v) for v in all_plugins.values())
    if total == 0:
        console.print("  [dim]No plugins found.[/dim]")
        console.print()
    console.print(
        f"[dim]Total: {total} plugin(s) across {sum(1 for v in all_plugins.values() if v)} type(s)[/dim]"
    )
    console.print()
    console.print("[dim]Use [bold]pip install <package>[/bold] to install more plugins.[/dim]")
    console.print()


@plugin.command(name="info")
@click.argument("name")
def plugin_info(name: str):
    """Show details for a specific plugin by name.

    Scans all plugin groups (strategies, factors, workflows) for
    the given name and shows the first match.
    """
    from polymind.core.discover import discover_all

    all_plugins = discover_all()
    for kind, items in all_plugins.items():
        if name in items:
            cls = items[name]
            console.print(f"\n[bold]{name}[/bold]")
            console.print(f"  Type:   {kind.rstrip('s').capitalize()}")
            console.print(f"  Module: {cls.__module__}")
            console.print(f"  Class:  {cls.__qualname__}")
            doc = cls.__doc__ or "No documentation"
            console.print(f"  Doc:    {doc.strip()}")
            console.print()
            return

    console.print(f"[red]Plugin '{name}' not found.[/red]")
    console.print("[dim]Use [bold]polymind plugin list[/bold] to see all installed plugins.[/dim]")
    console.print()


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
