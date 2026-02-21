"""Main CLI entry point."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from loguru import logger

from .client import GatewayClient
from .redis_cli import RedisManager
from .health import HealthChecker

# Create CLI app
app = typer.Typer(
    name="secure-agent",
    help="Management CLI for Secure Agent Architecture",
    add_completion=False,
)

# Console for pretty output
console = Console()

# Global config - Use Docker service names when running inside container
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")


@app.command()
def health(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch health status continuously"),
):
    """
    Check system health status.

    Checks all components: gateway, adaptor channel, agent, Redis, LiteLLM, Squid, and connections.
    """
    import asyncio
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    async def check_health():
        checker = HealthChecker(
            redis_host=REDIS_HOST,
            redis_port=REDIS_PORT,
            redis_password=REDIS_PASSWORD or None,
            gateway_url=GATEWAY_URL,
            litellm_url=os.getenv("LITELM_URL", "http://litellm:4000"),
            squid_host=os.getenv("SQUID_HOST", "squid"),
            squid_port=int(os.getenv("SQUID_PORT", "3128")),
        )

        return await checker.check_all()

    def format_health_result(result: dict, verbose: bool = False) -> Panel:
        """Format health result as a Rich panel."""

        # Main status table
        table = Table(title="Secure Agent Health Check", show_header=True)
        table.add_column("Component", style="cyan", width=20)
        table.add_column("Status", width=12)
        table.add_column("Response Time", justify="right", width=14)
        if verbose:
            table.add_column("Details")

        # Status colors
        status_colors = {
            "healthy": "green",
            "degraded": "yellow",
            "unhealthy": "red",
        }

        # Overall status
        overall_status = result.get("status", "unknown")
        overall_color = status_colors.get(overall_status, "white")

        checks = result.get("checks", {})
        for component, check_data in checks.items():
            status = check_data.get("status", "unknown")
            status_str = f"[{status_colors.get(status, 'white')}]{status.upper()}[/{status_colors.get(status, 'white')}]"
            response_time = f"{check_data.get('response_time_ms', 0):.1f} ms"

            if verbose:
                details = check_data.get("details", {})
                detail_str = ""
                if isinstance(details, dict):
                    # Format details nicely
                    if component == "redis":
                        detail_str = f"v{details.get('version', '?')}, {details.get('db_size', 0)} keys"
                    elif component == "agent":
                        detail_str = f"tasks: {details.get('completed_tasks', 0)}"
                    elif component == "adaptor_channel":
                        detail_str = f"queue: {details.get('queue_length', 0)}"
                    elif component == "connections":
                        conn_count = len(details.get('connections', {}))
                        detail_str = f"{conn_count} checked"
                    else:
                        # Show message if available
                        detail_str = check_data.get('message', '')
                else:
                    detail_str = str(details)[:30]

                table.add_row(
                    component.replace("_", " ").title(),
                    status_str,
                    response_time,
                    detail_str[:30] if detail_str else "",
                )
            else:
                table.add_row(
                    component.replace("_", " ").title(),
                    status_str,
                    response_time,
                )

        # Create panel
        timestamp = result.get("timestamp", "")
        timestamp_str = timestamp[:19].replace("T", " ") if timestamp else ""

        panel = Panel(
            table,
            title=f"[bold]System Status: [{overall_color}]{overall_status.upper()}[/{overall_color}][/] - {timestamp_str}",
            border_style=overall_color,
        )

        return panel

    async def watch_mode():
        """Watch health status continuously."""
        try:
            with Live(console, refresh_per_second=1) as live:
                while True:
                    result = await check_health()
                    panel = format_health_result(result, verbose)
                    live.update(panel)
                    await asyncio.sleep(2)
        except KeyboardInterrupt:
            console.print("\n[yellow]Health monitoring stopped[/yellow]")

    async def single_check():
        """Run a single health check."""
        try:
            result = await check_health()
            panel = format_health_result(result, verbose)
            console.print(panel)

            # Show verbose details separately if requested
            if verbose:
                console.print("\n[bold]Detailed Information:[/bold]")
                checks = result.get("checks", {})
                for component, check_data in checks.items():
                    console.print(f"\n[bold cyan]{component.replace('_', ' ').title()}:[/bold cyan]")
                    console.print(f"  Status: {check_data.get('status', 'unknown')}")
                    console.print(f"  Message: {check_data.get('message', 'N/A')}")
                    details = check_data.get("details", {})
                    if details:
                        for key, value in details.items():
                            if key != "connections":
                                console.print(f"  {key}: {value}")
                        # Show connections separately
                        if "connections" in details:
                            console.print("  Connections:")
                            for conn_name, conn_data in details["connections"].items():
                                status = "[green]✓[/green]" if conn_data.get("healthy") else "[red]✗[/red]"
                                latency = conn_data.get("latency_ms")
                                console.print(f"    {status} {conn_name}: {latency}ms" if latency else f"    {status} {conn_name}")

        except Exception as e:
            console.print(f"[bold red]Error checking health:[/bold red] {e}")
            logger.exception("Health check failed")
            sys.exit(1)

    if watch:
        asyncio.run(watch_mode())
    else:
        asyncio.run(single_check())


@app.command()
def submit(
    input: str = typer.Argument(..., help="Input text for the agent"),
    task_id: Optional[str] = typer.Option(None, "--task-id", "-t", help="Task ID"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Config JSON"),
):
    """Submit a task to the agent."""
    import asyncio
    import json

    cfg = json.loads(config) if config else None

    async def do_submit():
        client = GatewayClient(GATEWAY_URL)
        try:
            result = await client.submit_task(input, task_id, cfg)
            await client.close()

            console.print(f"[bold green]Task submitted:[/bold green]")
            console.print(f"  Task ID: {result.get('task_id')}")
            console.print(f"  Status: {result.get('status')}")

            if result.get("error"):
                console.print(f"[bold red]Error:[/bold red] {result['error']}")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(1)

    asyncio.run(do_submit())


@app.command()
def result(
    task_id: str = typer.Argument(..., help="Task ID"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch until completion"),
):
    """Get task result."""
    import asyncio

    async def get_result():
        client = GatewayClient(GATEWAY_URL)
        try:
            if watch:
                await client.watch_task(task_id)
            else:
                result = await client.get_result(task_id)
                await client.close()

                console.print(f"[bold]Task ID:[/bold] {task_id}")
                console.print(f"[bold]Status:[/bold] {result.get('status')}")

                if result.get("result"):
                    console.print(f"\n[bold green]Result:[/bold green]")
                    console.print(result["result"])
                elif result.get("error"):
                    console.print(f"\n[bold red]Error:[/bold red] {result['error']}")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(1)

    asyncio.run(get_result())


@app.command()
def config(
    key: str = typer.Argument(..., help="Config key"),
    value: Optional[str] = typer.Argument(None, help="Config value (JSON)"),
):
    """Get or set config."""
    import json

    manager = RedisManager(REDIS_HOST, REDIS_PORT, REDIS_PASSWORD or None)
    manager.connect()

    try:
        if value:
            # Set config
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value
            manager.set_config(key, parsed_value)
            console.print(f"[bold green]Set config:[/bold green] {key}")
        else:
            # Get config
            cfg = manager.get_config(key)
            if cfg is not None:
                console.print(f"[bold]Config:[/bold] {key}")
                console.print(json.dumps(cfg, indent=2))
            else:
                console.print(f"[yellow]Config not found:[/yellow] {key}")
    finally:
        manager.disconnect()


@app.command()
def tasks():
    """List all tasks."""
    manager = RedisManager(REDIS_HOST, REDIS_PORT, REDIS_PASSWORD or None)
    manager.connect()

    try:
        task_ids = manager.list_tasks()

        if task_ids:
            table = Table(title="Tasks")
            table.add_column("Task ID", style="cyan")
            table.add_column("Status", style="green")

            for task_id in task_ids:
                task = manager.get_task(task_id)
                status = task.get("status", "unknown") if task else "not_found"
                table.add_row(task_id, status)

            console.print(table)
        else:
            console.print("[yellow]No tasks found[/yellow]")
    finally:
        manager.disconnect()


@app.command()
def queue(
    clear: bool = typer.Option(False, "--clear", help="Clear the queue"),
):
    """Show or clear the agent queue."""
    manager = RedisManager(REDIS_HOST, REDIS_PORT, REDIS_PASSWORD or None)
    manager.connect()

    try:
        if clear:
            typer.confirm("Are you sure you want to clear the queue?", abort=True)
            manager.clear_queue()
            console.print("[bold green]Queue cleared[/bold green]")
        else:
            length = manager.get_queue_length()
            console.print(f"[bold]Queue length:[/bold] {length}")
    finally:
        manager.disconnect()


@app.command()
def setup():
    """Setup environment files."""
    env_file = Path(".env")

    if env_file.exists():
        console.print("[yellow].env file already exists[/yellow]")
        if not typer.confirm("Overwrite?"):
            return

    env_content = """# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_secure_password_here

# LiteLLM Configuration
LITELM_MASTER_KEY=your_litellm_master_key_here

# API Keys (for LiteLLM)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...

# Gateway URL
GATEWAY_URL=http://localhost:8080
"""

    env_file.write_text(env_content)
    console.print(f"[bold green]Created .env file[/bold green]")
    console.print("[yellow]Please edit the values before running the system[/yellow]")


if __name__ == "__main__":
    app()
