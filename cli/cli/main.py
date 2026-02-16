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

# Create CLI app
app = typer.Typer(
    name="secure-agent",
    help="Management CLI for Secure Agent Architecture",
    add_completion=False,
)

# Console for pretty output
console = Console()

# Global config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")


@app.command()
def health():
    """Check system health."""
    import asyncio

    async def check():
        client = GatewayClient(GATEWAY_URL)
        try:
            result = await client.health()
            await client.close()

            table = Table(title="System Health")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")

            for key, value in result.items():
                status = "✓" if value else "✗"
                table.add_row(key, status)

            console.print(table)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(1)

    asyncio.run(check())


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
