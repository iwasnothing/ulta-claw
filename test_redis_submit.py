#!/usr/bin/env python3
"""Test agent by submitting task to Redis queue."""

import asyncio
import json
import uuid
import sys
sys.path.insert(0, '/raid/llm-data/scripts/ulta-claw')

import redis.asyncio as redis
from loguru import logger


async def test_agent():
    """Test the agent by submitting a task to Redis queue."""
    logger.info("Connecting to Redis...")

    r = redis.Redis(
        host="localhost",
        port=6379,
        password="",
        decode_responses=True,
    )

    await r.ping()
    logger.info("Connected to Redis")

    # Create a test skill
    task_id = str(uuid.uuid4())
    logger.info(f"Creating test task: {task_id}")

    skill_markdown = """# test_hello

## What This Skill Does

Greets the user with a friendly message.

## When This Should Be Used

When the user says hello or asks for a greeting.

## Instructions

1. Say hello to the user
2. Provide a friendly greeting message
3. Keep it brief and cheerful
"""

    # Store skill
    await r.set("skill:test_hello", skill_markdown)
    await r.sadd("skills:index", "test_hello")
    logger.info("Created test skill")

    # Submit task to queue
    task_data = {
        "task_id": task_id,
        "input": "Say hello to me",
        "config": {},
    }

    await r.set(f"task:{task_id}", json.dumps(task_data))
    await r.lpush("agent:queue", task_id)
    logger.info(f"Submitted task to queue")

    # Wait for completion
    logger.info("Waiting for task completion...")
    for i in range(30):
        await asyncio.sleep(2)

        # Check task status
        task = await r.get(f"task:{task_id}")
        if task:
            task_obj = json.loads(task)
            status = task_obj.get("status")

            logger.info(f"Status check {i+1}: {status}")

            if status == "completed":
                # Get result
                result = await r.get(f"result:{task_id}")
                if result:
                    result_obj = json.loads(result)
                    logger.info("\n" + "="*50)
                    logger.info(f"TASK COMPLETED: {task_id}")
                    logger.info("="*50)
                    logger.info(f"Result:\n{result_obj.get('result', 'No result')}")
                    logger.info("="*50)
                    break
            elif status == "failed":
                result = await r.get(f"result:{task_id}")
                if result:
                    result_obj = json.loads(result)
                    logger.error(f"Task failed: {result_obj.get('error', 'Unknown error')}")
                break

    # Cleanup
    await r.delete("skill:test_hello")
    await r.srem("skills:index", "test_hello")
    await r.delete(f"task:{task_id}")
    await r.delete(f"result:{task_id}")
    await r.close()
    logger.info("Test complete")


if __name__ == "__main__":
    asyncio.run(test_agent())
