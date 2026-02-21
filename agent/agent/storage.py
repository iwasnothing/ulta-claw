"""Redis storage for secure agent."""

import json
import re
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

    # Skill management methods

    def _parse_skill_markdown(self, skill_name: str, skill_markdown: str) -> Dict[str, str]:
        """
        Parse skill markdown to extract name, description, condition, and full content.

        Args:
            skill_name: Name of the skill
            skill_markdown: The markdown string

        Returns:
            Dictionary with name, description, condition, and full markdown
        """
        logger.debug(f"Parsing skill markdown for '{skill_name}' ({len(skill_markdown)} chars)")
        logger.debug(f"Skill markdown first 500 chars:\n{skill_markdown[:500]}")

        # Extract sections using regex
        description_match = re.search(r'##?\s*What.*Skill\s*Does?\s*\n(.*?)(?=##|\n\n|\Z)', skill_markdown, re.IGNORECASE | re.DOTALL)
        condition_match = re.search(r'##?\s*When.*Should\s*Be\s*Used\s*\n(.*?)(?=##|\n\n|\Z)', skill_markdown, re.IGNORECASE | re.DOTALL)

        description = description_match.group(1).strip() if description_match else ""
        condition = condition_match.group(1).strip() if condition_match else ""

        if not description:
            logger.warning(f"Skill '{skill_name}': description regex did not match — falling back to first non-heading line")
            lines = [l.strip() for l in skill_markdown.split("\n") if l.strip() and not l.strip().startswith("#")]
            description = lines[0] if lines else f"Skill: {skill_name}"

        if not condition:
            logger.warning(f"Skill '{skill_name}': condition regex did not match — using skill name as hint")
            condition = f"When '{skill_name}' capability is needed"

        logger.debug(f"Parsed skill '{skill_name}' — description: {description!r}, condition: {condition!r}")

        return {
            "name": skill_name,
            "description": description,
            "condition": condition,
            "full_markdown": skill_markdown,
        }

    async def create_skill(
        self,
        skill_name: str,
        skill_markdown: str
    ) -> bool:
        """
        Create a new skill in Redis.

        The skill is stored as a complete markdown string.

        Args:
            skill_name: Unique name for the skill
            skill_markdown: Complete markdown string with:
                1. What Skill does
                2. When it should be used
                3. Step-by-step instructions
                4. Optional supporting resources

        Returns:
            True if successful, False otherwise
        """
        skill_key = f"skill:{skill_name}"

        try:
            # Store full skill markdown
            await self.redis.set(skill_key, skill_markdown)

            # Add to skills index set
            await self.redis.sadd("skills:index", skill_name)

            logger.info(f"Created skill: {skill_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create skill {skill_name}: {e}")
            return False

    async def get_skill(self, skill_name: str) -> Optional[str]:
        """
        Get a skill by name from Redis.

        Returns the full markdown string.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill markdown string or None if not found
        """
        skill_key = f"skill:{skill_name}"
        try:
            skill_markdown = await self.redis.get(skill_key)
            return skill_markdown
        except Exception as e:
            logger.error(f"Failed to get skill {skill_name}: {e}")
            return None

    async def get_all_skills(self) -> Dict[str, str]:
        """
        Get all skills from Redis (full markdown strings).

        Returns:
            Dictionary mapping skill names to full markdown strings
        """
        try:
            skill_names = await self.redis.smembers("skills:index")
            skills = {}

            for skill_name in skill_names:
                skill_markdown = await self.get_skill(skill_name)
                if skill_markdown:
                    skills[skill_name] = skill_markdown

            logger.info(f"Retrieved {len(skills)} skills")
            return skills
        except Exception as e:
            logger.error(f"Failed to get all skills: {e}")
            return {}

    async def get_skill_catalog(self) -> str:
        """
        Get skill catalog (name, description, and condition to use only).

        Parses markdown to extract only the relevant sections for orchestration.

        Returns:
            Formatted string with skill catalog
        """
        skills = await self.get_all_skills()

        if not skills:
            logger.warning("No skills found in Redis — catalog will be empty")
            return "No skills available."

        logger.info(f"Building skill catalog from {len(skills)} skills: {list(skills.keys())}")

        catalog_lines = ["Available Skills:\n"]
        for skill_name, skill_markdown in skills.items():
            parsed = self._parse_skill_markdown(skill_name, skill_markdown)

            catalog_lines.append(f"- {skill_name}")
            catalog_lines.append(f"  Description: {parsed['description']}")
            catalog_lines.append(f"  When to use: {parsed['condition']}")
            catalog_lines.append("")

        catalog = "\n".join(catalog_lines)
        logger.info(f"Final skill catalog:\n{catalog}")

        return catalog

    async def delete_skill(self, skill_name: str) -> bool:
        """
        Delete a skill from Redis.

        Args:
            skill_name: Name of the skill to delete

        Returns:
            True if successful, False otherwise
        """
        skill_key = f"skill:{skill_name}"

        try:
            # Delete skill data
            result = await self.redis.delete(skill_key)

            # Remove from index
            await self.redis.srem("skills:index", skill_name)

            if result:
                logger.info(f"Deleted skill: {skill_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete skill {skill_name}: {e}")
            return False

    async def list_skill_names(self) -> list[str]:
        """
        List all skill names.

        Returns:
            List of skill names
        """
        try:
            skill_names = await self.redis.smembers("skills:index")
            return sorted(list(skill_names))
        except Exception as e:
            logger.error(f"Failed to list skill names: {e}")
            return []
