"""FastAPI backend for Secure Agent Health Check UI."""

import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cli.health import HealthChecker

# Initialize FastAPI
app = FastAPI(
    title="Secure Agent Health Check API",
    description="REST API for monitoring Secure Agent system health",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global config - Docker service names
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_USERNAME = os.getenv("REDIS_USER", None)
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
LITELM_URL = os.getenv("LITELM_URL", "http://litellm:4000")
SQUID_HOST = os.getenv("SQUID_HOST", "squid")
SQUID_PORT = int(os.getenv("SQUID_PORT", "3128"))


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Secure Agent Health Check API", "version": "1.0.0"}


@app.get("/api/health")
async def get_health() -> dict[str, Any]:
    """
    Get system health status.

    Returns comprehensive health check results for all components.
    """
    checker = HealthChecker(
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT,
        redis_password=REDIS_PASSWORD or None,
        redis_username=REDIS_USERNAME,
        gateway_url=GATEWAY_URL,
        litellm_url=LITELM_URL,
        squid_host=SQUID_HOST,
        squid_port=SQUID_PORT,
    )
    result = await checker.check_all()
    return result


@app.get("/api/health/verbose")
async def get_health_verbose() -> dict[str, Any]:
    """
    Get detailed system health status.

    Returns verbose health check results including all details.
    """
    result = await get_health()
    # Already includes details from the health check
    return result


@app.get("/api/components")
async def get_components() -> dict[str, list[str]]:
    """Get list of all health check components."""
    return {
        "components": [
            "gateway",
            "adaptor_channel",
            "agent",
            "redis",
            "litellm",
            "squid",
            "connections",
        ]
    }


@app.get("/api/config")
async def get_config() -> dict[str, str | int]:
    """Get current health check configuration."""
    return {
        "redis_host": REDIS_HOST,
        "redis_port": REDIS_PORT,
        "gateway_url": GATEWAY_URL,
        "litellm_url": LITELM_URL,
        "squid_host": SQUID_HOST,
        "squid_port": SQUID_PORT,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
