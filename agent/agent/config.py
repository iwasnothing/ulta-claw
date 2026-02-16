"""Configuration management for secure agent."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """Agent configuration loaded from environment."""

    # Redis settings
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = "default"
    redis_db: int = 0

    # LiteLLM settings
    litellm_endpoint: str = "http://litellm:4000"
    litellm_key: str = "agent_key_123"

    # Proxy settings (enforced by Docker)
    http_proxy: str = "http://squid:3128"
    https_proxy: str = "http://squid:3128"
    no_proxy: str = "redis,litellm,localhost"

    # Agent settings
    model_name: str = "claude-3-sonnet"
    max_tokens: int = 4096
    temperature: float = 0.7
    max_retries: int = 3

    # Queue settings
    queue_poll_interval: float = 1.0  # seconds
    task_timeout: int = 300  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global config instance
_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config


def validate_network_isolation() -> bool:
    """Verify that network isolation is enforced."""
    config = get_config()

    # Check if proxy settings are present
    http_proxy = os.getenv("http_proxy")
    https_proxy = os.getenv("https_proxy")

    if not http_proxy or not https_proxy:
        raise RuntimeError("Network isolation not enforced: proxy not set")

    # Verify proxy points to Squid
    if "squid" not in http_proxy.lower() or "squid" not in https_proxy.lower():
        raise RuntimeError("Network isolation not enforced: invalid proxy")

    return True
