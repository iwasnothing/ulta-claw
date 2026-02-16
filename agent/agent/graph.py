"""LangGraph-based agent implementation."""

import asyncio
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from loguru import logger

from .llm import SecureLLM
from .storage import SecureStorage


class AgentState(dict):
    """State for LangGraph agent."""

    input: str
    messages: list
    result: Optional[str] = None
    error: Optional[str] = None


class SecureAgent:
    """Secure LangGraph agent."""

    def __init__(self):
        self.llm = SecureLLM()
        self.storage = SecureStorage()
        self.graph = self._build_graph()

    async def initialize(self):
        """Initialize agent components."""
        await self.storage.connect()
        logger.info("Secure agent initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("process", self._process_node)
        graph.add_node("validate", self._validate_node)

        # Add edges
        graph.set_entry_point("process")
        graph.add_edge("process", "validate")

        # Conditional edges
        graph.add_conditional_edges(
            "validate",
            self._should_retry,
            {
                "process": "process",
                "end": END,
            },
        )

        return graph.compile()

    async def _process_node(self, state: AgentState) -> AgentState:
        """Process the input with LLM."""
        try:
            # Add input to messages
            messages = state.get("messages", [])
            messages.append(HumanMessage(content=state["input"]))

            # Generate response
            response = await self.llm.chat(messages)
            messages.append(AIMessage(content=response))

            state["messages"] = messages
            state["result"] = response

            logger.info(f"Processed input, got {len(response)} chars")

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            state["error"] = str(e)

        return state

    async def _validate_node(self, state: AgentState) -> AgentState:
        """Validate the result."""
        # Simple validation - ensure result is not empty
        if state.get("result") and len(state["result"]) > 0:
            logger.info("Validation passed")
        else:
            state["error"] = "Empty or invalid result"

        return state

    def _should_retry(self, state: AgentState) -> str:
        """Determine if we should retry processing."""
        if state.get("error") and "retry" not in str(state.get("messages", [])):
            # Simple retry logic
            return "process"
        return "end"

    async def run(self, input_data: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run the agent with input.

        Args:
            input_data: Input string for the agent
            config: Optional configuration overrides

        Returns:
            Result dictionary
        """
        initial_state = AgentState(
            input=input_data,
            messages=[],
            result=None,
            error=None,
        )

        # Apply config overrides
        if config:
            initial_state.update(config)

        # Run graph
        try:
            final_state = await self.graph.ainvoke(initial_state)

            if final_state.get("error"):
                logger.warning(f"Agent completed with error: {final_state['error']}")
            else:
                logger.info("Agent completed successfully")

            return {
                "result": final_state.get("result"),
                "error": final_state.get("error"),
                "messages": len(final_state.get("messages", [])),
            }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {
                "result": None,
                "error": str(e),
                "messages": 0,
            }

    async def process_task(self, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task from Redis queue.

        Args:
            task_id: Task ID
            task_data: Task data including input and config

        Returns:
            Processing result
        """
        # Update status to processing
        await self.storage.update_task_status(task_id, "processing")

        # Run agent
        result = await self.run(
            input_data=task_data.get("input", ""),
            config=task_data.get("config"),
        )

        # Update status
        if result.get("error"):
            await self.storage.update_task_status(task_id, "failed", result)
        else:
            await self.storage.update_task_status(task_id, "completed", result)
            await self.storage.store_result(task_id, result)

        return result

    async def run_forever(self):
        """Continuously process tasks from the queue."""
        logger.info("Starting agent queue processing loop")

        while True:
            try:
                # Get task from queue
                task_id = await self.storage.pop_task_from_queue()

                if task_id:
                    logger.info(f"Processing task: {task_id}")

                    # Get task data
                    task_data = await self.storage.get_task(task_id)

                    if task_data:
                        # Process task
                        await self.process_task(task_id, task_data)
                    else:
                        logger.warning(f"Task data not found: {task_id}")
                else:
                    # No tasks, sleep
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                logger.info("Queue processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(1)

    async def shutdown(self):
        """Shutdown agent components."""
        await self.storage.disconnect()
        logger.info("Agent shutdown complete")
