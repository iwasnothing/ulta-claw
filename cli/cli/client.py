"""HTTP client for interacting with the gateway."""

import httpx
from typing import Optional, Dict, Any
from loguru import logger


class GatewayClient:
    """Client for communicating with the secure gateway."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def health(self) -> Dict[str, Any]:
        """Check gateway health."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "error", "error": str(e)}

    async def submit_task(
        self,
        input_data: str,
        task_id: Optional[str] = None,
        config: Optional[Dict] = None,
        auth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a task to the agent.

        Args:
            input_data: Input for the agent
            task_id: Optional task ID
            config: Optional config
            auth_token: Optional auth token

        Returns:
            Response from gateway
        """
        import uuid

        task_id = task_id or str(uuid.uuid4())

        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        payload = {
            "task_id": task_id,
            "input": {"text": input_data},
            "config": config,
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/task",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Task submission failed: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "error": str(e),
            }

    async def get_result(
        self,
        task_id: str,
    ) -> Dict[str, Any]:
        """
        Get task result from gateway.

        Args:
            task_id: Task ID

        Returns:
            Task result
        """
        try:
            response = await self.client.get(f"{self.base_url}/task/{task_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"task_id": task_id, "status": "not_found"}
            raise
        except Exception as e:
            logger.error(f"Get result failed: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "error": str(e),
            }

    async def watch_task(
        self,
        task_id: str,
        interval: float = 1.0,
    ):
        """
        Watch a task until completion.

        Args:
            task_id: Task ID
            interval: Poll interval in seconds
        """
        import asyncio

        from rich.console import Console
        from rich.live import Live
        from rich.panel import Panel

        console = Console()

        with Live(console, refresh_per_second=4) as live:
            while True:
                result = await self.get_result(task_id)
                status = result.get("status", "unknown")

                panel = Panel(
                    f"[bold]Task ID:[/bold] {task_id}\n"
                    f"[bold]Status:[/bold] {status}\n",
                    title="Task Status",
                    border_style="blue" if status != "completed" else "green",
                )

                live.update(panel)

                if status in ["completed", "failed", "error"]:
                    # Show final result
                    if status == "completed" and result.get("result"):
                        console.print("\n[bold green]Result:[/bold green]")
                        console.print(result["result"])
                    elif status in ["failed", "error"] and result.get("error"):
                        console.print(f"\n[bold red]Error:[/bold red] {result['error']}")

                    live.stop()
                    break

                await asyncio.sleep(interval)
