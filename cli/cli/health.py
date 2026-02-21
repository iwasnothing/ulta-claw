"""Health check module for Secure Agent Architecture."""

import asyncio
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import httpx
import redis
from loguru import logger

from .client import GatewayClient
from .redis_cli import RedisManager


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    component: str
    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    response_time_ms: float
    details: Optional[dict[str, Any]] = None


class HealthChecker:
    """Comprehensive health checker for the Secure Agent system."""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        redis_username: Optional[str] = None,
        gateway_url: str = "http://localhost:8080",
        litellm_url: str = "http://localhost:4000",
        squid_host: str = "localhost",
        squid_port: int = 3128,
        check_timeout: float = 5.0,
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_username = redis_username
        self.gateway_url = gateway_url.rstrip("/")
        self.litellm_url = litellm_url.rstrip("/")
        self.squid_host = squid_host
        self.squid_port = squid_port
        self.check_timeout = check_timeout
        self.results: list[HealthCheckResult] = []

    async def check_all(self) -> dict[str, Any]:
        """
        Run all health checks.

        Returns:
            Dictionary with overall status and detailed results
        """
        self.results = []
        tasks = [
            self.check_gateway(),
            self.check_adaptor_channel(),
            self.check_agent(),
            self.check_redis(),
            self.check_litellm(),
            self.check_squid(),
            self.check_connections(),
        ]

        # Collect results from all health checks
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for result in completed:
            if isinstance(result, Exception):
                logger.error(f"Health check failed with exception: {result}")
            elif isinstance(result, HealthCheckResult):
                self.results.append(result)

        # Determine overall status
        unhealthy = [r for r in self.results if r.status == "unhealthy"]
        degraded = [r for r in self.results if r.status == "degraded"]

        if unhealthy:
            overall_status = "unhealthy"
        elif degraded:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {r.component: self._result_to_dict(r) for r in self.results},
        }

    async def check_gateway(self) -> HealthCheckResult:
        """Check gateway health via HTTP endpoint."""
        start_time = time.time()
        details = {}

        try:
            client = GatewayClient(self.gateway_url)

            # Test health endpoint
            response = await client.health()
            await client.close()

            # Check response structure
            if response.get("error"):
                return HealthCheckResult(
                    component="gateway",
                    status="unhealthy",
                    message=f"Gateway returned error: {response['error']}",
                    response_time_ms=(time.time() - start_time) * 1000,
                    details=response,
                )

            # Extract status from response
            gateway_status = response.get("status", "unknown")
            details.update(response)

            response_time = (time.time() - start_time) * 1000

            if gateway_status == "ok" or gateway_status == "healthy":
                return HealthCheckResult(
                    component="gateway",
                    status="healthy",
                    message="Gateway is operational",
                    response_time_ms=response_time,
                    details=details,
                )
            else:
                return HealthCheckResult(
                    component="gateway",
                    status="degraded",
                    message=f"Gateway status: {gateway_status}",
                    response_time_ms=response_time,
                    details=details,
                )

        except httpx.ConnectError:
            return HealthCheckResult(
                component="gateway",
                status="unhealthy",
                message="Cannot connect to gateway",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.TimeoutException:
            return HealthCheckResult(
                component="gateway",
                status="unhealthy",
                message="Gateway timeout",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Gateway health check error: {e}")
            return HealthCheckResult(
                component="gateway",
                status="unhealthy",
                message=f"Unexpected error: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_adaptor_channel(self) -> HealthCheckResult:
        """
        Check adaptor channel status.
        The adaptor channel is the communication path between gateway and agent.
        We check Redis queues and pub/sub status.
        """
        start_time = time.time()
        details = {}

        try:
            redis_manager = RedisManager(
                self.redis_host, self.redis_port, self.redis_password or None, username=self.redis_username
            )
            redis_manager.connect()

            # Check queue exists
            queue_length = redis_manager.get_queue_length()
            details["queue_length"] = queue_length

            # Check for recent activity
            recent_tasks = redis_manager.list_tasks()
            details["total_tasks"] = len(recent_tasks)

            redis_manager.disconnect()

            response_time = (time.time() - start_time) * 1000

            # Adaptor channel is healthy if we can access the queue
            return HealthCheckResult(
                component="adaptor_channel",
                status="healthy",
                message=f"Queue accessible, {queue_length} pending tasks",
                response_time_ms=response_time,
                details=details,
            )

        except redis.ConnectionError as e:
            return HealthCheckResult(
                component="adaptor_channel",
                status="unhealthy",
                message=f"Cannot connect to adaptor channel: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Adaptor channel health check error: {e}")
            return HealthCheckResult(
                component="adaptor_channel",
                status="unhealthy",
                message=f"Unexpected error: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_agent(self) -> HealthCheckResult:
        """
        Check agent runtime status.
        The agent doesn't expose HTTP, so we check:
        1. Agent heartbeat in Redis (if available)
        2. Agent status in Redis (if available)
        3. Task queue connectivity (as proxy for agent activity)
        """
        start_time = time.time()
        details = {}

        try:
            redis_manager = RedisManager(
                self.redis_host, self.redis_port, self.redis_password or None, username=self.redis_username
            )
            redis_manager.connect()

            # Check agent heartbeat (optional - agent may not implement this)
            heartbeat_key = "agent:heartbeat"
            heartbeat = redis_manager.client.get(heartbeat_key)
            details["heartbeat"] = heartbeat

            # Check agent status (optional)
            status_key = "agent:status"
            status = redis_manager.client.get(status_key)
            details["status"] = status

            # Check recent completed tasks
            completed_key = "agent:completed:count"
            completed_count = redis_manager.client.get(completed_key)
            details["completed_tasks"] = int(completed_count) if completed_count else 0

            redis_manager.disconnect()

            response_time = (time.time() - start_time) * 1000

            # If heartbeat exists, check if it's recent
            if heartbeat:
                try:
                    heartbeat_time = datetime.fromisoformat(heartbeat)
                    age = (datetime.utcnow() - heartbeat_time).total_seconds()
                    details["heartbeat_age_seconds"] = age

                    if age < 60:
                        agent_status_str = status or "active"
                        return HealthCheckResult(
                            component="agent",
                            status="healthy",
                            message=f"Agent is {agent_status_str}",
                            response_time_ms=response_time,
                            details=details,
                        )
                    else:
                        return HealthCheckResult(
                            component="agent",
                            status="degraded",
                            message=f"Agent heartbeat is stale ({age:.1f}s old)",
                            response_time_ms=response_time,
                            details=details,
                        )
                except (ValueError, TypeError):
                    pass

            # No heartbeat but agent queue is accessible - assume agent is running
            # (The agent doesn't currently implement a heartbeat mechanism)
            return HealthCheckResult(
                component="agent",
                status="healthy",
                message="Agent is running (no heartbeat data)",
                response_time_ms=response_time,
                details=details,
            )

        except redis.ConnectionError as e:
            return HealthCheckResult(
                component="agent",
                status="unhealthy",
                message=f"Cannot check agent status: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Agent health check error: {e}")
            return HealthCheckResult(
                component="agent",
                status="unhealthy",
                message=f"Unexpected error: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis server health."""
        start_time = time.time()
        details = {}

        try:
            # Test basic connection
            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                username=self.redis_username,
                password=self.redis_password,
                decode_responses=True,
                socket_timeout=self.check_timeout,
            )

            # Ping test
            ping_result = client.ping()
            if not ping_result:
                return HealthCheckResult(
                    component="redis",
                    status="unhealthy",
                    message="Redis ping failed",
                    response_time_ms=(time.time() - start_time) * 1000,
                )

            # Get info
            info = client.info()
            details["version"] = info.get("redis_version", "unknown")
            details["used_memory_human"] = info.get("used_memory_human", "unknown")
            details["connected_clients"] = info.get("connected_clients", 0)

            # Check database size
            db_size = client.dbsize()
            details["db_size"] = db_size

            client.close()

            response_time = (time.time() - start_time) * 1000

            return HealthCheckResult(
                component="redis",
                status="healthy",
                message=f"Redis {details['version']}, {db_size} keys",
                response_time_ms=response_time,
                details=details,
            )

        except redis.AuthenticationError:
            return HealthCheckResult(
                component="redis",
                status="unhealthy",
                message="Redis authentication failed",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except redis.ConnectionError as e:
            return HealthCheckResult(
                component="redis",
                status="unhealthy",
                message=f"Cannot connect to Redis: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Redis health check error: {e}")
            return HealthCheckResult(
                component="redis",
                status="unhealthy",
                message=f"Unexpected error: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_litellm(self) -> HealthCheckResult:
        """Check LiteLLM proxy health using /v1/models endpoint."""
        start_time = time.time()
        details = {}

        try:
            async with httpx.AsyncClient(timeout=self.check_timeout) as client:
                # Test using /v1/models endpoint (list available models)
                response = await client.get(f"{self.litellm_url}/v1/models")
                response.raise_for_status()

                response_time = (time.time() - start_time) * 1000
                data = response.json()

                details["status_code"] = response.status_code
                model_count = len(data.get("data", []))
                details["model_count"] = model_count
                if model_count > 0:
                    # List first few model names
                    details["models"] = [m.get("id") for m in data.get("data", [])[:5]]

                return HealthCheckResult(
                    component="litellm",
                    status="healthy",
                    message=f"LiteLLM proxy is operational ({model_count} models available)",
                    response_time_ms=response_time,
                    details=details,
                )

        except httpx.ConnectError:
            return HealthCheckResult(
                component="litellm",
                status="unhealthy",
                message="Cannot connect to LiteLLM proxy",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.TimeoutException:
            return HealthCheckResult(
                component="litellm",
                status="unhealthy",
                message="LiteLLM proxy timeout",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.HTTPStatusError as e:
            return HealthCheckResult(
                component="litellm",
                status="unhealthy",
                message=f"LiteLLM returned error: {e.response.status_code}",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"LiteLLM health check error: {e}")
            return HealthCheckResult(
                component="litellm",
                status="unhealthy",
                message=f"Unexpected error: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_squid(self) -> HealthCheckResult:
        """Check Squid proxy health."""
        start_time = time.time()
        details = {}

        try:
            # Test TCP connection to Squid
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.check_timeout)

            connection_result = sock.connect_ex((self.squid_host, self.squid_port))
            sock.close()

            response_time = (time.time() - start_time) * 1000

            if connection_result == 0:
                details["port"] = self.squid_port
                details["host"] = self.squid_host
                return HealthCheckResult(
                    component="squid",
                    status="healthy",
                    message=f"Squid proxy is listening on port {self.squid_port}",
                    response_time_ms=response_time,
                    details=details,
                )
            else:
                return HealthCheckResult(
                    component="squid",
                    status="unhealthy",
                    message=f"Squid proxy is not reachable (port {self.squid_port})",
                    response_time_ms=response_time,
                    details=details,
                )

        except socket.timeout:
            return HealthCheckResult(
                component="squid",
                status="unhealthy",
                message="Squid proxy connection timeout",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Squid health check error: {e}")
            return HealthCheckResult(
                component="squid",
                status="unhealthy",
                message=f"Unexpected error: {e}",
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def check_connections(self) -> HealthCheckResult:
        """
        Check network connections between components.
        Tests connectivity from various vantage points.
        """
        start_time = time.time()
        details = {"connections": {}}
        all_healthy = True

        # Test connections
        connection_tests = [
            ("cli_to_redis", self._test_redis_connection),
            ("cli_to_gateway", self._test_gateway_connection),
            ("cli_to_litellm", self._test_litellm_connection),
            ("cli_to_squid", self._test_squid_connection),
        ]

        for name, test_func in connection_tests:
            try:
                result = await test_func()
                details["connections"][name] = result
                if not result.get("healthy", False):
                    all_healthy = False
            except Exception as e:
                details["connections"][name] = {"healthy": False, "error": str(e)}
                all_healthy = False

        response_time = (time.time() - start_time) * 1000

        if all_healthy:
            return HealthCheckResult(
                component="connections",
                status="healthy",
                message="All network connections are operational",
                response_time_ms=response_time,
                details=details,
            )
        else:
            return HealthCheckResult(
                component="connections",
                status="degraded",
                message="Some network connections are failing",
                response_time_ms=response_time,
                details=details,
            )

    async def _test_redis_connection(self) -> dict:
        """Test CLI to Redis connection."""
        try:
            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                username=self.redis_username,
                password=self.redis_password,
                socket_timeout=2.0,
            )
            start = time.time()
            client.ping()
            latency = (time.time() - start) * 1000
            client.close()
            return {"healthy": True, "latency_ms": round(latency, 2)}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _test_gateway_connection(self) -> dict:
        """Test CLI to Gateway connection."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                start = time.time()
                response = await client.get(f"{self.gateway_url}/health")
                latency = (time.time() - start) * 1000
                return {
                    "healthy": response.status_code < 500,
                    "latency_ms": round(latency, 2),
                    "status_code": response.status_code,
                }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _test_litellm_connection(self) -> dict:
        """Test CLI to LiteLLM connection."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                start = time.time()
                response = await client.get(f"{self.litellm_url}/v1/models")
                latency = (time.time() - start) * 1000
                return {
                    "healthy": response.status_code < 500,
                    "latency_ms": round(latency, 2),
                    "status_code": response.status_code,
                }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _test_squid_connection(self) -> dict:
        """Test CLI to Squid connection."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            start = time.time()
            result = sock.connect_ex((self.squid_host, self.squid_port))
            latency = (time.time() - start) * 1000
            sock.close()
            return {
                "healthy": result == 0,
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def _result_to_dict(self, result: HealthCheckResult) -> dict:
        """Convert HealthCheckResult to dictionary."""
        return {
            "status": result.status,
            "message": result.message,
            "response_time_ms": round(result.response_time_ms, 2),
            "details": result.details,
        }
