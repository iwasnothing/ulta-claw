#!/usr/bin/env python3
"""Test script for Observational Memory integration."""

import asyncio
import sys
sys.path.insert(0, '/raid/llm-data/scripts/ulta-claw')

from agent.agent.storage import SecureStorage
from agent.agent.graph import AgentState, SecureAgent
from loguru import logger


async def create_test_skill(storage: SecureStorage):
    """Create a simple test skill."""
    skill_markdown = """# test_search

## What This Skill Does

Performs a web search using Perplexity API to find current information.

## When This Should Be Used

When the user needs up-to-date information, facts, or research from the internet.

## Instructions

1. Use the perplexity_search tool with the user's query
2. Analyze the search results
3. Provide a concise summary of the findings
4. If the search fails, explain the error

## Supporting Resources

Use the perplexity_search tool with the query: {query}
"""

    await storage.create_skill("test_search", skill_markdown)
    logger.info("Created test skill: test_search")


async def test_om_workflow():
    """Test the Observational Memory workflow."""
    logger.info("Starting Observational Memory workflow test")

    # Initialize components
    agent = SecureAgent()
    await agent.initialize()
    storage = agent.storage

    # Create test skill
    await create_test_skill(storage)

    # Test 1: Simple query that will trigger skill execution
    logger.info("\n=== Test 1: Simple query ===")
    result1 = await agent.run("What is the current weather in Tokyo?")
    logger.info(f"Result 1: {result1.get('result', 'No result')[:200]}...")

    # Test 2: Another query to see if observations are used
    logger.info("\n=== Test 2: Second query (checking OM) ===")
    result2 = await agent.run("What about the weather in London?")
    logger.info(f"Result 2: {result2.get('result', 'No result')[:200]}...")

    # Test 3: Check if observations are being built
    logger.info("\n=== Test 3: Query with no skills ===")
    result3 = await agent.run("Hello, how are you?")
    logger.info(f"Result 3: {result3.get('result', 'No result')}")

    # Cleanup
    await storage.delete_skill("test_search")
    await agent.shutdown()
    logger.info("\nTest completed!")


if __name__ == "__main__":
    asyncio.run(test_om_workflow())
