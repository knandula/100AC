#!/usr/bin/env python
"""
100AC CLI - Command-line interface for managing agents and workflows.

Usage:
    python cli.py agent list
    python cli.py agent info <agent_id>
    
    python cli.py workflow list
    python cli.py workflow run <workflow_name>
    python cli.py workflow history
    python cli.py workflow stats
    
    python cli.py system status
    python cli.py system health
    
    python cli.py test all      # Run full test suite
    python cli.py test agents   # Test agent communication
    python cli.py test data     # Test data collection
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from loguru import logger

from shared.config import init_config
from shared.message_bus import init_message_bus, get_message_bus
from shared.database.connection import init_database, get_database
from agents.registry import init_registry, get_registry
from agents.orchestrator import init_orchestrator, get_orchestrator
from agents.test_agent import TestAgent
from agents.data.market_data_fetcher import MarketDataFetcher
from agents.data.historical_data_loader import HistoricalDataLoader
from orchestrator.workflow_loader import init_loader, get_loader
from orchestrator.workflow_scheduler import init_scheduler, get_scheduler
from orchestrator.workflow_state import init_state_manager, get_state_manager


console = Console()


@click.group()
def cli():
    """100AC - 100 Micro Agents for Financial Markets"""
    pass


@cli.group()
def agent():
    """Manage agents"""
    pass


@cli.group()
def workflow():
    """Manage workflows"""
    pass


@cli.group()
def system():
    """System management"""
    pass


@cli.group()
def test():
    """Run system tests and demos"""
    pass


@agent.command("list")
def agent_list():
    """List all available agents"""
    async def _list():
        await init_system()
        registry = get_registry()
        
        table = Table(title="Available Agents")
        table.add_column("Agent ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Capabilities", style="magenta")
        table.add_column("Status", style="blue")
        
        for agent in registry.get_all_agents():
            capabilities = ", ".join([c.name for c in agent.metadata.capabilities])
            health = agent.get_health()
            table.add_row(
                agent.agent_id,
                agent.metadata.name,
                agent.metadata.category,
                capabilities,
                health.status.value,
            )
        
        console.print(table)
        await shutdown_system()
    
    asyncio.run(_list())


@agent.command("info")
@click.argument("agent_id")
def agent_info(agent_id):
    """Show detailed agent information"""
    async def _info():
        await init_system()
        registry = get_registry()
        
        agent = registry.get(agent_id)
        if not agent:
            console.print(f"[red]Agent '{agent_id}' not found[/red]")
            return
        
        console.print(Panel.fit(
            f"[bold cyan]{agent.metadata.name}[/bold cyan]\n"
            f"[dim]{agent.metadata.description}[/dim]",
            title=f"Agent: {agent_id}"
        ))
        
        # Capabilities
        table = Table(title="Capabilities")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="green")
        
        for cap in agent.metadata.capabilities:
            table.add_row(cap.name, cap.description)
        
        console.print(table)
        
        # Health
        health = agent.get_health()
        console.print(f"\n[bold]Health:[/bold]")
        console.print(f"  Status: {health.status.value}")
        console.print(f"  Messages Processed: {health.messages_processed}")
        console.print(f"  Errors: {health.errors_count}")
        console.print(f"  Avg Response Time: {health.average_response_time_ms:.2f}ms")
        
        await shutdown_system()
    
    asyncio.run(_info())


@workflow.command("list")
def workflow_list():
    """List all available workflows"""
    loader = init_loader()
    workflows = loader.list_workflows()
    
    if not workflows:
        console.print("[yellow]No workflows found[/yellow]")
        return
    
    table = Table(title="Available Workflows")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Steps", style="magenta")
    
    for w in workflows:
        table.add_row(w["name"], w["description"], str(w["steps"]))
    
    console.print(table)


@workflow.command("run")
@click.argument("workflow_name")
@click.option("--params", "-p", help="JSON parameters", default="{}")
def workflow_run(workflow_name, params):
    """Run a workflow"""
    import json
    
    async def _run():
        await init_system()
        
        loader = get_loader()
        workflow = loader.load_workflow_by_name(workflow_name)
        
        if not workflow:
            console.print(f"[red]Workflow '{workflow_name}' not found[/red]")
            await shutdown_system()
            return
        
        console.print(f"[bold cyan]Running workflow: {workflow.name}[/bold cyan]")
        
        try:
            context = json.loads(params) if params != "{}" else None
            
            orchestrator = get_orchestrator()
            result = await orchestrator.execute_workflow(workflow, context)
            
            console.print("[bold green]✓ Workflow completed successfully![/bold green]")
            console.print("\n[bold]Results:[/bold]")
            for step_id, step_result in result.items():
                console.print(f"  {step_id}: {step_result}")
        
        except Exception as e:
            console.print(f"[bold red]✗ Workflow failed: {e}[/bold red]")
        
        await shutdown_system()
    
    asyncio.run(_run())


@workflow.command("history")
@click.option("--limit", "-l", default=10, help="Number of records to show")
def workflow_history(limit):
    """Show workflow execution history"""
    async def _history():
        db = init_database()
        await db.initialize()
        
        state_manager = init_state_manager()
        history = await state_manager.get_workflow_history(limit=limit)
        
        if not history:
            console.print("[yellow]No workflow execution history[/yellow]")
            return
        
        table = Table(title=f"Workflow Execution History (Last {limit})")
        table.add_column("Workflow", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Started", style="yellow")
        table.add_column("Duration", style="magenta")
        
        for record in history:
            duration = f"{record['duration_seconds']:.2f}s" if record['duration_seconds'] else "running"
            status_color = "green" if record['status'] == "completed" else ("red" if record['status'] == "failed" else "yellow")
            table.add_row(
                record['workflow_name'],
                f"[{status_color}]{record['status']}[/{status_color}]",
                record['started_at'][:19],
                duration,
            )
        
        console.print(table)
    
    asyncio.run(_history())


@workflow.command("stats")
def workflow_stats():
    """Show workflow execution statistics"""
    async def _stats():
        db = init_database()
        await db.initialize()
        
        state_manager = init_state_manager()
        stats = await state_manager.get_statistics()
        
        console.print(Panel.fit(
            f"[bold]Total Executions:[/bold] {stats['total_executions']}\n"
            f"[bold green]Completed:[/bold green] {stats['completed']}\n"
            f"[bold red]Failed:[/bold red] {stats['failed']}\n"
            f"[bold yellow]Running:[/bold yellow] {stats['running']}\n"
            f"[bold]Success Rate:[/bold] {stats['success_rate']:.1f}%\n"
            f"[bold]Avg Duration:[/bold] {stats['average_duration_seconds']:.2f}s",
            title="Workflow Statistics"
        ))
    
    asyncio.run(_stats())


@system.command("status")
def system_status():
    """Show system status"""
    async def _status():
        await init_system()
        registry = get_registry()
        
        # Agent status
        agent_table = Table(title="Agent Status")
        agent_table.add_column("Agent", style="cyan")
        agent_table.add_column("Status", style="green")
        agent_table.add_column("Messages", style="yellow")
        agent_table.add_column("Errors", style="red")
        
        for agent in registry.get_all_agents():
            health = agent.get_health()
            agent_table.add_row(
                agent.metadata.name,
                health.status.value,
                str(health.messages_processed),
                str(health.errors_count),
            )
        
        console.print(agent_table)
        
        # Message bus status
        bus = get_message_bus()
        console.print(f"\n[bold]Message Bus:[/bold] Active")
        console.print(f"  Messages in history: {len(bus._message_history)}")
        
        await shutdown_system()
    
    asyncio.run(_status())


@system.command("health")
def system_health():
    """Run system health check"""
    async def _health():
        console.print("[bold cyan]Running system health check...[/bold cyan]\n")
        
        checks = []
        
        # Check 1: Initialize system
        try:
            await init_system()
            checks.append(("System Initialization", True, "OK"))
        except Exception as e:
            checks.append(("System Initialization", False, str(e)))
            return
        
        # Check 2: Database
        try:
            db = get_database()
            async with db.get_session() as session:
                await session.execute("SELECT 1")
            checks.append(("Database Connection", True, "OK"))
        except Exception as e:
            checks.append(("Database Connection", False, str(e)))
        
        # Check 3: Message Bus
        try:
            bus = get_message_bus()
            if bus._running:
                checks.append(("Message Bus", True, "Running"))
            else:
                checks.append(("Message Bus", False, "Not running"))
        except Exception as e:
            checks.append(("Message Bus", False, str(e)))
        
        # Check 4: Agents
        try:
            registry = get_registry()
            agent_count = len(registry.get_all_agents())
            checks.append(("Agents Registered", True, f"{agent_count} agents"))
        except Exception as e:
            checks.append(("Agents Registered", False, str(e)))
        
        # Display results
        table = Table(title="Health Check Results")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="yellow")
        
        all_ok = True
        for component, status, details in checks:
            status_str = "[green]✓[/green]" if status else "[red]✗[/red]"
            table.add_row(component, status_str, details)
            if not status:
                all_ok = False
        
        console.print(table)
        
        if all_ok:
            console.print("\n[bold green]✓ All systems operational[/bold green]")
        else:
            console.print("\n[bold red]✗ Some systems have issues[/bold red]")
        
        await shutdown_system()
    
    asyncio.run(_health())


async def init_system():
    """Initialize all system components"""
    # Suppress logger output for CLI
    logger.remove()
    
    init_config()
    message_bus = init_message_bus()
    await message_bus.start()
    
    db = init_database()
    await db.initialize()
    
    registry = init_registry()
    
    # Register agents
    test_agent = TestAgent()
    registry.register(test_agent)
    
    market_fetcher = MarketDataFetcher()
    registry.register(market_fetcher)
    
    historical_loader = HistoricalDataLoader()
    registry.register(historical_loader)
    
    # Start agents
    await registry.start_all()
    
    init_orchestrator()
    init_loader()
    init_scheduler()
    init_state_manager()


async def shutdown_system():
    """Shutdown all system components"""
    registry = get_registry()
@test.command("all")
def test_all():
    """Run comprehensive system test suite"""
    async def _test():
        from rich.panel import Panel
        
        # Display header
        console.print()
        console.print(Panel.fit(
            "[bold cyan]100AC - 100 Micro Agents for Financial Markets[/bold cyan]\n"
            "[dim]Workflow Engine v1.0 - 2/12 Agents, 4 Workflows[/dim]",
            border_style="blue"
        ))
        console.print()
        
        # Initialize system
        console.print("[bold blue]Initializing system...[/bold blue]")
        await init_system()
        
        # Show system status
        console.print("\n[bold cyan]System Status:[/bold cyan]")
        registry = get_registry()
        table = Table()
        table.add_column("Agent", style="cyan")
        table.add_column("Status", style="green")
        
        for agent in registry.get_all_agents():
            health = agent.get_health()
            table.add_row(agent.metadata.name, health.status.value)
        
        console.print(table)
        
        # Test 1: Basic Communication
        console.print("\n[bold yellow]Test 1: Agent Communication[/bold yellow]")
        orchestrator = get_orchestrator()
        
        try:
            result = await orchestrator.execute_simple_request(
                agent_id="test_agent",
                action="echo",
                parameters={"message": "Hello, 100AC!"},
                timeout=5.0,
            )
            console.print(f"  ✓ Echo: {result.get('message', result)}")
        except Exception as e:
            console.print(f"  ✗ Error: {e}")
        
        try:
            result = await orchestrator.execute_simple_request(
                agent_id="test_agent",
                action="add",
                parameters={"a": 10, "b": 32},
                timeout=5.0,
            )
            console.print(f"  ✓ Add: {result.get('result', result)}")
        except Exception as e:
            console.print(f"  ✗ Error: {e}")
        
        # Test 2: Market Data
        console.print("\n[bold yellow]Test 2: Market Data Fetching[/bold yellow]")
        
        try:
            result = await orchestrator.execute_simple_request(
                agent_id="market_data_fetcher",
                action="fetch_price",
                parameters={"symbol": "AAPL"},
                timeout=10.0,
            )
            if "error" not in result:
                console.print(f"  ✓ AAPL: ${result.get('price', 'N/A')}")
            else:
                console.print(f"  ✗ Error: {result['error']}")
        except Exception as e:
            console.print(f"  ✗ Exception: {e}")
        
        try:
            result = await orchestrator.execute_simple_request(
                agent_id="market_data_fetcher",
                action="fetch_batch",
                parameters={"symbols": ["AAPL", "MSFT", "GOOGL"]},
                timeout=15.0,
            )
            if "quotes" in result:
                console.print(f"  ✓ Batch: {len(result['quotes'])} symbols fetched")
                for quote in result['quotes'][:3]:
                    if "error" not in quote:
                        console.print(f"    - {quote['symbol']}: ${quote.get('price', 'N/A')}")
            else:
                console.print(f"  ✗ Unexpected format")
        except Exception as e:
            console.print(f"  ✗ Exception: {e}")
        
        # Test 3: Historical Data
        console.print("\n[bold yellow]Test 3: Historical Data Loading[/bold yellow]")
        
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            result = await orchestrator.execute_simple_request(
                agent_id="historical_data_loader",
                action="load_history",
                parameters={
                    "symbol": "AAPL",
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "interval": "1d"
                },
                timeout=15.0,
            )
            if "error" not in result:
                bars = result.get('history') or result.get('data', [])
                console.print(f"  ✓ AAPL: {len(bars)} bars loaded")
            else:
                console.print(f"  ✗ Error: {result['error']}")
        except Exception as e:
            console.print(f"  ✗ Exception: {e}")
        
        # Test 4: Workflows
        console.print("\n[bold yellow]Test 4: Workflow Execution[/bold yellow]")
        
        loader = get_loader()
        
        try:
            workflow = loader.load_workflow_by_name("simple_test")
            if workflow:
                result = await orchestrator.execute_workflow(workflow)
                console.print(f"  ✓ simple_test: {len(result)} steps completed")
        except Exception as e:
            console.print(f"  ✗ Error: {e}")
        
        try:
            workflow = loader.load_workflow_by_name("market_data_pipeline")
            if workflow:
                result = await orchestrator.execute_workflow(workflow)
                console.print(f"  ✓ market_data_pipeline: completed successfully")
        except Exception as e:
            console.print(f"  ✗ Error: {e}")
        
        console.print("\n[bold green]✓ All tests completed![/bold green]\n")
        
        await shutdown_system()
    
    asyncio.run(_test())


@test.command("agents")
def test_agents():
    """Test agent communication only"""
    async def _test():
        await init_system()
        orchestrator = get_orchestrator()
        
        console.print("[bold cyan]Testing Agent Communication...[/bold cyan]\n")
        
        # Echo test
        try:
            result = await orchestrator.execute_simple_request(
                agent_id="test_agent",
                action="echo",
                parameters={"message": "Test message"},
                timeout=5.0,
            )
            console.print(f"✓ Echo: {result.get('message', result)}")
        except Exception as e:
            console.print(f"✗ Echo failed: {e}")
        
        # Add test
        try:
            result = await orchestrator.execute_simple_request(
                agent_id="test_agent",
                action="add",
                parameters={"a": 5, "b": 7},
                timeout=5.0,
            )
            console.print(f"✓ Add: {result.get('result', result)}")
        except Exception as e:
            console.print(f"✗ Add failed: {e}")
        
        await shutdown_system()
    
    asyncio.run(_test())


@test.command("data")
def test_data():
    """Test data collection agents"""
    async def _test():
        await init_system()
        orchestrator = get_orchestrator()
        
        console.print("[bold cyan]Testing Data Collection...[/bold cyan]\n")
        
        # Market data
        try:
            result = await orchestrator.execute_simple_request(
                agent_id="market_data_fetcher",
                action="fetch_batch",
                parameters={"symbols": ["AAPL", "MSFT", "GOOGL"]},
                timeout=15.0,
            )
            if "quotes" in result:
                console.print(f"✓ Fetched {len(result['quotes'])} quotes:")
                for quote in result['quotes']:
                    if "error" not in quote:
                        console.print(f"  {quote['symbol']}: ${quote.get('price', 'N/A')}")
        except Exception as e:
            console.print(f"✗ Market data failed: {e}")
        
        # Historical data
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            result = await orchestrator.execute_simple_request(
                agent_id="historical_data_loader",
                action="load_history",
                parameters={
                    "symbol": "AAPL",
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "interval": "1d"
                },
                timeout=15.0,
            )
            if "error" not in result:
                bars = result.get('history') or result.get('data', [])
                console.print(f"✓ Historical: {len(bars)} bars loaded")
        except Exception as e:
            console.print(f"✗ Historical data failed: {e}")
        
        await shutdown_system()
    
    asyncio.run(_test())


async def shutdown_system():
    """Shutdown all system components"""
    registry = get_registry()
    await registry.stop_all()
    
    message_bus = get_message_bus()
    await message_bus.stop()


if __name__ == "__main__":
    cli()
