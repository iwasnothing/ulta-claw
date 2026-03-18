"""Memory layer for the agent using mem0 with FAISS vector store."""

import os
from typing import Optional, List, Dict, Any
from loguru import logger
from .config import get_config

try:
    from mem0 import Memory
except ImportError:
    logger.error("mem0ai package not found. Install it with: pip install mem0ai")
    raise


class AgentMemory:
    """
    Memory layer for the agent using mem0 with FAISS as vector store.

    Uses local embedding model via LiteLLM proxy for embeddings.
    Stores memory in FAISS vector database for efficient similarity search.
    """

    def __init__(
        self,
        user_id: str = "default_user",
        memory_dir: Optional[str] = None,
    ):
        """
        Initialize the agent memory.

        Args:
            user_id: User ID for memory isolation
            memory_dir: Directory to store FAISS index (defaults to config)
        """
        self.config_obj = get_config()
        self.user_id = user_id
        self.memory_dir = memory_dir or self.config_obj.memory_dir

        # Ensure memory directory exists
        os.makedirs(self.memory_dir, exist_ok=True)

        # Initialize mem0 with FAISS vector store
        self.config = {
            "vector_store": {
                "provider": "faiss",
                "config": {
                    "dimension": 3072,  # Dimension for gemma-300m embeddings
                    "save_path": self.memory_dir,
                    "index_type": "Flat",  # Use flat index for exact search
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": self.config_obj.embedding_model,
                    "api_base": self.config_obj.embedding_api_base,
                    "api_key": "sk-dummy-token",
                }
            }
        }

        self.memory: Optional[Memory] = None
        logger.info(f"Memory initialized with FAISS store at {self.memory_dir}")

    async def initialize(self):
        """Initialize the memory connection."""
        try:
            # Create mem0 Memory instance
            self.memory = Memory.from_config(self.config)
            logger.info("Memory layer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            raise

    async def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Add a memory to the store.

        Args:
            content: Content of the memory
            metadata: Optional metadata associated with the memory
            user_id: User ID for this memory (defaults to instance user_id)

        Returns:
            Memory ID if successful, None otherwise
        """
        try:
            if not self.memory:
                await self.initialize()

            # Prepare metadata
            final_metadata = metadata or {}
            final_metadata["user_id"] = user_id or self.user_id

            # Add memory
            result = self.memory.add(
                content,
                user_id=user_id or self.user_id,
                metadata=final_metadata,
            )

            logger.debug(f"Added memory: {content[:100]}...")
            return result

        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return None

    async def get_all(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get all memories for a user.

        Args:
            user_id: User ID (defaults to instance user_id)
            limit: Maximum number of memories to return

        Returns:
            List of memory dictionaries
        """
        try:
            if not self.memory:
                await self.initialize()

            # Get all memories
            memories = self.memory.get_all(user_id=user_id or self.user_id)

            # Limit results
            if limit and len(memories) > limit:
                memories = memories[:limit]

            logger.debug(f"Retrieved {len(memories)} memories")
            return memories

        except Exception as e:
            logger.error(f"Failed to get all memories: {e}")
            return []

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memories.

        Args:
            query: Search query
            user_id: User ID (defaults to instance user_id)
            limit: Maximum number of results to return
            threshold: Similarity threshold (0-1)

        Returns:
            List of relevant memories
        """
        try:
            if not self.memory:
                await self.initialize()

            # Search memories
            results = self.memory.search(
                query=query,
                user_id=user_id or self.user_id,
                limit=limit,
            )

            # Filter by threshold
            filtered_results = []
            for result in results:
                score = result.get("score", 0)
                if score >= threshold:
                    filtered_results.append(result)

            logger.debug(f"Found {len(filtered_results)} relevant memories for query: {query[:100]}...")
            return filtered_results

        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    async def delete(
        self,
        memory_id: str,
    ) -> bool:
        """
        Delete a memory by ID.

        Args:
            memory_id: ID of the memory to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.memory:
                await self.initialize()

            # Delete memory
            self.memory.delete(memory_id)

            logger.debug(f"Deleted memory: {memory_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False

    async def update(
        self,
        memory_id: str,
        new_content: str,
    ) -> bool:
        """
        Update a memory's content.

        Args:
            memory_id: ID of the memory to update
            new_content: New content for the memory

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.memory:
                await self.initialize()

            # Update memory
            self.memory.update(memory_id, new_content)

            logger.debug(f"Updated memory: {memory_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update memory {memory_id}: {e}")
            return False

    async def get_context(
        self,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """
        Get a formatted context string from recent memories.

        Args:
            user_id: User ID (defaults to instance user_id)
            limit: Maximum number of memories to include

        Returns:
            Formatted context string
        """
        try:
            memories = await self.get_all(user_id=user_id, limit=limit)

            if not memories:
                return ""

            # Format memories as context
            context_lines = ["## Relevant Memories\n"]
            for i, memory in enumerate(memories, 1):
                content = memory.get("memory", "")
                metadata = memory.get("metadata", {})
                context_lines.append(f"{i}. {content}")
                if metadata:
                    context_lines.append(f"   (Metadata: {metadata})")

            return "\n".join(context_lines)

        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return ""

    async def add_conversation(
        self,
        user_message: str,
        agent_response: str,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Add a conversation turn to memory.

        Args:
            user_message: User's message
            agent_response: Agent's response
            user_id: User ID (defaults to instance user_id)

        Returns:
            Memory ID if successful, None otherwise
        """
        try:
            content = f"User: {user_message}\nAgent: {agent_response}"
            metadata = {
                "type": "conversation",
                "user_message": user_message,
                "agent_response": agent_response,
            }

            return await self.add(content, metadata=metadata, user_id=user_id)

        except Exception as e:
            logger.error(f"Failed to add conversation: {e}")
            return None

    async def clear_all(
        self,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Clear all memories for a user.

        Args:
            user_id: User ID (defaults to instance user_id)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.memory:
                await self.initialize()

            # Get all memories for the user
            memories = await self.get_all(user_id=user_id, limit=1000)

            # Delete each memory
            for memory in memories:
                memory_id = memory.get("id")
                if memory_id:
                    await self.delete(memory_id)

            logger.info(f"Cleared {len(memories)} memories for user {user_id or self.user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
            return False

    async def get_stats(
        self,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get memory statistics.

        Args:
            user_id: User ID (defaults to instance user_id)

        Returns:
            Dictionary with memory statistics
        """
        try:
            memories = await self.get_all(user_id=user_id, limit=10000)

            # Count by type
            type_counts = {}
            for memory in memories:
                metadata = memory.get("metadata", {})
                mem_type = metadata.get("type", "general")
                type_counts[mem_type] = type_counts.get(mem_type, 0) + 1

            return {
                "total_memories": len(memories),
                "memory_dir": self.memory_dir,
                "user_id": user_id or self.user_id,
                "type_counts": type_counts,
            }

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {
                "total_memories": 0,
                "memory_dir": self.memory_dir,
                "user_id": user_id or self.user_id,
                "type_counts": {},
            }
