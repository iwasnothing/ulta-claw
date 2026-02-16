"""Redis storage for secure agent."""

import json
from typing import Optional, Any, Dict
import redis.asyncio as redis
from loguru import logger
from .config import get_config


class SecureStorage:
    """Secure Redis storage with ACL-based access control."""

    def __init__(self):
        self.config = get_config()
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis with authentication."""
        try:
            self.redis = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                password=self.config.redis_password,
                db=self.config.redis_db,
                decode_responses=True,
            )
            await self.redis.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task from Redis.

        Args:
            task_id: Task ID

        Returns:
            Task data or None if not found
        """
        key = f"task:{task_id}"
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None

    async def update_task_status(
        self, task_id: str, status: str, result: Optional[Any] = None
    ):
        """
        Update task status in Redis.

        Args:
            task_id: Task ID
            status: New status (processing, completed, failed)
            result: Optional result data
        """
        key = f"task:{task_id}"
        try:
            data = await self.redis.get(key)
            if data:
                task = json.loads(data)
                task["status"] = status
                if result is not None:
                    task["result"] = result
                await self.redis.set(key, json.dumps(task))
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")

    async def store_result(self, task_id: str, result: Any):
        """
        Store task result in Redis.

        Args:
            task_id: Task ID
            result: Result data
        """
        key = f"result:{task_id}"
        try:
            await self.redis.set(key, json.dumps(result))
            logger.info(f"Stored result for task {task_id}")
        except Exception as e:
            logger.error(f"Failed to store result {task_id}: {e}")

    async def get_result(self, task_id: str) -> Optional[Any]:
        """
        Get task result from Redis.

        Args:
            task_id: Task ID

        Returns:
            Result data or None if not found
        """
        key = f"result:{task_id}"
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get result {task_id}: {e}")
            return None

    async def pop_task_from_queue(self) -> Optional[str]:
        """
        Pop a task from the agent queue.

        Returns:
            Task ID or None if queue is empty
        """
        try:
            task_id = await self.redis.brpop("agent:queue", timeout=1)
            if task_id:
                return task_id[1]  # brpop returns (key, value)
            return None
        except Exception as e:
            logger.error(f"Failed to pop from queue: {e}")
            return None

    async def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get config value from Redis.

        Args:
            key: Config key
            default: Default value if not found

        Returns:
            Config value
        """
        config_key = f"config:{key}"
        try:
            data = await self.redis.get(config_key)
            if data:
                return json.loads(data)
            return default
        except Exception as e:
            logger.error(f"Failed to get config {key}: {e}")
            return default
