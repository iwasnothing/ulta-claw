"""Main entry point for secure agent."""

import asyncio
import signal
import sys
from loguru import logger

from .agent import SecureAgent
from .config import get_config, validate_network_isolation


async def main():
    """Main agent loop."""
    # Configure logging
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    # Get configuration
    config = get_config()
    logger.info(f"Starting secure agent v0.1.0")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"LiteLLM endpoint: {config.litellm_endpoint}")

    # Validate network isolation
    try:
        validate_network_isolation()
        logger.info("Network isolation validated")
    except RuntimeError as e:
        logger.error(f"Security violation: {e}")
        sys.exit(1)

    # Initialize agent
    agent = SecureAgent()
    await agent.initialize()

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run agent in background
    run_task = asyncio.create_task(agent.run_forever())

    # Wait for shutdown
    await shutdown_event.wait()

    # Cancel run task
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass

    # Shutdown agent
    await agent.shutdown()
    logger.info("Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
