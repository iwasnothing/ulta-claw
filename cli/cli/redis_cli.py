"""Redis management utilities for CLI."""

import json
import redis
from typing import Optional, Any
from loguru import logger


class RedisManager:
    """Manager for Redis operations."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        username: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.username = username
        self.db = db
        self.client: Optional[redis.Redis] = None

    def connect(self):
        """Connect to Redis."""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                db=self.db,
                decode_responses=True,
            )
            self.client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from Redis")

    def get_config(self, key: str) -> Optional[Any]:
        """Get config value."""
        try:
            data = self.client.get(f"config:{key}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get config {key}: {e}")
            return None

    def set_config(self, key: str, value: Any):
        """Set config value."""
        try:
            self.client.set(f"config:{key}", json.dumps(value))
            logger.info(f"Set config {key}")
        except Exception as e:
            logger.error(f"Failed to set config {key}: {e}")
            raise

    def list_tasks(self) -> list[str]:
        """List all task IDs."""
        try:
            keys = self.client.keys("task:*")
            return [k.replace("task:", "") for k in keys]
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []

    def get_task(self, task_id: str) -> Optional[dict]:
        """Get task data."""
        try:
            data = self.client.get(f"task:{task_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None

    def delete_task(self, task_id: str):
        """Delete a task."""
        try:
            self.client.delete(f"task:{task_id}")
            self.client.delete(f"result:{task_id}")
            logger.info(f"Deleted task {task_id}")
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            raise

    def get_queue_length(self) -> int:
        """Get queue length."""
        try:
            return self.client.llen("agent:queue")
        except Exception as e:
            logger.error(f"Failed to get queue length: {e}")
            return 0

    def clear_queue(self):
        """Clear the agent queue."""
        try:
            length = self.client.delete("agent:queue")
            logger.info(f"Cleared queue ({length} items)")
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            raise

    def flush_all(self):
        """Flush all data (dangerous)."""
        try:
            self.client.flushdb()
            logger.warning("Flushed all data")
        except Exception as e:
            logger.error(f"Failed to flush: {e}")
            raise
