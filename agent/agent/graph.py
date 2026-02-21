"""LangGraph-based agentic workflow implementation."""

import asyncio
import operator
from typing import Dict, Any, Optional, Annotated
from langgraph.graph import StateGraph, END
from loguru import logger

from .llm import SecureLLM
from .storage import SecureStorage
from .orchestration_agent import OrchestrationAgent, OrchestrationState
from .skill_execution_agent import SkillExecutionAgent


class AgentState(dict):
    """State for LangGraph agent."""

    # --- Observational Memory Variables ---
    # Stable, condensed log of what has happened across the whole session
    observations: str = ""
    # Volatile history where recent user messages and massive skill outputs are dumped
    raw_message_history: Annotated[list, operator.add] = []

    # --- Workflow Variables ---
    user_message: str
    user_intent: str = ""
    action_plan: list = []
    next_skill: Optional[str] = None
    skill_results: list = []
    current_step: int = 0
    final_response: Optional[str] = None
    error: Optional[str] = None


class SecureAgent:
    """Secure LangGraph agent with orchestration and skill execution."""

    def __init__(self):
        self.orchestrator = OrchestrationAgent()
        self.skill_executor = SkillExecutionAgent()
        self.storage = SecureStorage()
        self.graph = self._build_graph()

    async def initialize(self):
        """Initialize agent components."""
        await self.orchestrator.initialize()
        await self.skill_executor.initialize()
        await self.storage.connect()
        logger.info("Secure agent initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph for agentic workflow."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("orchestrate", self._orchestrate_node)
        graph.add_node("execute_skill", self._execute_skill_node)
        graph.add_node("check_complete", self._check_complete_node)
        graph.add_node("summarize", self._summarize_node)
        graph.add_node("no_skills_response", self._no_skills_response_node)
        graph.add_node("observer", self._observer_node)
        graph.add_node("reflector", self._reflector_node)

        # Add edges
        graph.set_entry_point("orchestrate")
        graph.add_edge("orchestrate", "check_complete")

        # Conditional edges after orchestration
        graph.add_conditional_edges(
            "check_complete",
            self._should_execute_skills,
            {
                "execute": "execute_skill",
                "no_skills": "no_skills_response",
                "summarize": "summarize",
            },
        )

        # After skill execution, route based on OM thresholds and action plan
        graph.add_conditional_edges(
            "execute_skill",
            self._route_after_skill_execution,
            {
                "reflector": "reflector",
                "observer": "observer",
                "summarize": "summarize",
                "execute_skill": "execute_skill",
            },
        )

        # After observer or reflector, route back to skill execution or summarize
        # Both memory cleanup nodes should route back to the same evaluation point
        graph.add_conditional_edges(
            "observer",
            self._route_after_skill_execution,
            {
                "reflector": "reflector",
                "observer": "observer",
                "summarize": "summarize",
                "execute_skill": "execute_skill",
            },
        )

        graph.add_conditional_edges(
            "reflector",
            self._route_after_skill_execution,
            {
                "reflector": "reflector",
                "observer": "observer",
                "summarize": "summarize",
                "execute_skill": "execute_skill",
            },
        )

        # After no skills response or summarize, we're done
        graph.add_edge("no_skills_response", END)
        graph.add_edge("summarize", END)

        return graph.compile()

    async def _orchestrate_node(self, state: AgentState) -> AgentState:
        """
        Orchestrate the action plan based on user message.

        This node:
        1. Queries all skills from Redis
        2. Determines user intent
        3. Generates action plan
        4. Sets next skill to execute
        """
        try:
            user_message = state.get("user_message", "")
            observations = state.get("observations", "")
            logger.debug(f"Orchestrate node - user_message: {user_message[:200]}")
            logger.debug(f"Orchestrate node - observations length: {len(observations)}")

            # Use orchestration agent to determine action plan
            orchestration_state = await self.orchestrator.determine_action_plan(
                user_message=user_message,
                observations=observations
            )
            logger.debug(f"Orchestration state returned: {dict(orchestration_state)}")

            # Update state with orchestration results
            state["user_intent"] = orchestration_state.get("user_intent", "")
            state["action_plan"] = orchestration_state.get("action_plan", [])
            state["current_step"] = 0
            state["skill_results"] = []
            state["error"] = orchestration_state.get("error")

            # Get first skill to execute
            next_skill = await self.orchestrator.get_next_skill(orchestration_state)
            state["next_skill"] = next_skill

            logger.info(
                f"Orchestration complete - Intent: {state['user_intent']}, "
                f"Action plan: {state['action_plan']}, next_skill: {next_skill}"
            )

        except Exception as e:
            logger.error(f"Orchestration failed: {e}", exc_info=True)
            state["error"] = str(e)
            state["action_plan"] = []
            state["next_skill"] = None

        return state

    async def _check_complete_node(self, state: AgentState) -> AgentState:
        """
        Check if the action plan is complete or if no skills are needed.

        This node determines the next step based on:
        - Whether there are skills in the action plan
        - Whether all skills have been executed
        """
        # If there's an error, go to no_skills_response
        if state.get("error"):
            return state

        action_plan = state.get("action_plan", [])
        current_step = state.get("current_step", 0)

        # Check if we have skills to execute
        if not action_plan:
            logger.info("No skills in action plan")
            state["next_skill"] = None
            return state

        # Check if we've completed all skills
        if current_step >= len(action_plan):
            logger.info("All skills executed")
            state["next_skill"] = None
            return state

        return state

    async def _execute_skill_node(self, state: AgentState) -> AgentState:
        """
        Execute the next skill in the action plan.

        This node:
        1. Gets the next skill from state
        2. Retrieves full skill from Redis
        3. Executes the skill using the skill execution agent
        4. Records the result
        5. Advances to the next step
        """
        try:
            skill_name = state.get("next_skill")

            if not skill_name:
                logger.warning("No skill to execute")
                return state

            logger.debug(f"Executing skill: {skill_name} (step {state.get('current_step', 0)})")

            user_message = state.get("user_message", "")
            previous_results = state.get("skill_results", [])
            observations = state.get("observations", "")
            context = {
                "user_intent": state.get("user_intent", ""),
                "action_plan": state.get("action_plan", []),
                "current_step": state.get("current_step", 0),
            }

            logger.debug(f"Skill execution context: {context}")

            # Execute the skill
            result = await self.skill_executor.execute_skill(
                skill_name=skill_name,
                user_message=user_message,
                previous_results=previous_results,
                context=context,
                observations=observations
            )
            logger.debug(f"Skill execution result - output length: {len(result.get('output') or '')}, error: {result.get('error')}")

            # Append raw output to raw_message_history for OM processing
            if result.get("output"):
                raw_entry = f"[Skill Execution: {skill_name}]\n{result['output']}"
                state["raw_message_history"] = state.get("raw_message_history", []) + [raw_entry]
                logger.debug(f"Added raw output to message history: {len(result['output'])} chars")

            # Record the result
            await self.orchestrator.record_execution_result(
                state,
                skill_name=skill_name,
                output=result.get("output"),
                error=result.get("error")
            )

            # Advance to the next step
            await self.orchestrator.advance_step(state)

            # Update next_skill
            state["next_skill"] = state.get("next_skill")

            logger.info(f"Executed skill: {skill_name}, step: {state['current_step']}/{len(state['action_plan'])}")

        except Exception as e:
            logger.error(f"Skill execution failed: {e}")
            skill_name = state.get("next_skill", "unknown")

            # Append error to raw_message_history for OM processing
            error_entry = f"[Skill Execution Error: {skill_name}]\n{str(e)}"
            state["raw_message_history"] = state.get("raw_message_history", []) + [error_entry]
            logger.debug(f"Added error to message history: {len(str(e))} chars")

            await self.orchestrator.record_execution_result(
                state,
                skill_name=skill_name,
                output=None,
                error=str(e)
            )
            # Continue to next step even on error
            await self.orchestrator.advance_step(state)
            state["next_skill"] = state.get("next_skill")

        return state

    async def _summarize_node(self, state: AgentState) -> AgentState:
        """
        Summarize execution results and generate final response.

        This node:
        1. Takes all execution results
        2. Synthesizes them into a coherent response
        3. Generates the final response to the user
        """
        try:
            orchestration_state = OrchestrationState(
                user_message=state.get("user_message", ""),
                user_intent=state.get("user_intent", ""),
                action_plan=state.get("action_plan", []),
                current_step=state.get("current_step", 0),
                execution_results=state.get("skill_results", []),
            )

            # Generate summary response
            final_response = await self.orchestrator.summarize_results(orchestration_state)

            state["final_response"] = final_response

            logger.info("Summary generated")

        except Exception as e:
            logger.error(f"Summary failed: {e}")
            state["error"] = str(e)
            state["final_response"] = "I encountered an error while processing your request."

        return state

    async def _no_skills_response_node(self, state: AgentState) -> AgentState:
        """
        Generate a response when no skills are available to fulfill the user's intent.
        """
        state["final_response"] = "I have not equipped with required skills to fulfill your intent."
        logger.info("Generated no-skills response")
        return state

    async def _observer_node(self, state: AgentState) -> AgentState:
        """
        Observer node compresses raw_message_history into observations.

        This node:
        1. Takes the raw_message_history (potentially massive skill outputs)
        2. Compresses it into formatted text with emoji-based log levels
        3. Appends to observations
        4. Clears raw_message_history

        Emoji-based log levels:
        - 🚨 Critical: Errors, failures, important warnings
        - ⚠️ Important: Significant results, key findings
        - ℹ️ Informational: General progress, normal outputs
        """
        try:
            raw_history = state.get("raw_message_history", [])

            if not raw_history:
                logger.debug("Observer node: No raw message history to process")
                return state

            logger.info(f"Observer node: Compressing {len(raw_history)} raw messages")

            # Build system prompt for the observer LLM
            observer_system_prompt = """You are an observer that compresses conversation history into concise, structured logs.

Your job is to:
1. Review the raw conversation history
2. Extract the most important information
3. Format each item with an appropriate emoji log level:
   - 🚨 CRITICAL: Errors, failures, critical issues
   - ⚠️ IMPORTANT: Significant results, key findings, major successes
   - ℹ️ INFO: General progress, normal outputs, routine operations

Format each log entry as:
[EMOJI] Timestamp - Brief description: Key details

Keep entries concise. Focus on what actually happened and what matters for future context.
Ignore repetitive or trivial details.
"""

            # Combine raw history into a single string
            raw_text = "\n\n---\n\n".join(raw_history)

            # Use LLM to compress the raw history
            try:
                compressed = await self.orchestrator.llm.chat(
                    messages=[
                        {"role": "system", "content": observer_system_prompt},
                        {"role": "user", "content": f"Compress this conversation history:\n\n{raw_text}"},
                    ],
                    temperature=0.3,
                )

                # Append compressed logs to observations
                current_observations = state.get("observations", "")
                if current_observations:
                    state["observations"] = current_observations + "\n\n" + compressed
                else:
                    state["observations"] = compressed

                logger.info(f"Observer node: Added compressed logs to observations")

            except Exception as e:
                logger.error(f"Observer node LLM compression failed: {e}")
                # Fallback: simple compression without LLM
                fallback_compressed = f"\n\n[ℹ️] {len(raw_history)} messages processed"
                state["observations"] = state.get("observations", "") + fallback_compressed

            # Clear raw message history after compression
            state["raw_message_history"] = []
            logger.info("Observer node: Cleared raw message history")

        except Exception as e:
            logger.error(f"Observer node failed: {e}")
            # Don't fail the workflow - just log and continue

        return state

    async def _reflector_node(self, state: AgentState) -> AgentState:
        """
        Reflector node condenses observations when they grow too large.

        This node:
        1. Takes the current observations
        2. Merges related observations
        3. Extracts patterns
        4. Condenses aggressively to save tokens
        """
        try:
            observations = state.get("observations", "")

            if not observations or len(observations) < 10000:  # Only trigger if substantial
                logger.debug("Reflector node: Observations too small to condense")
                return state

            logger.info("Reflector node: Condensing observations")

            # Build system prompt for the reflector LLM
            reflector_system_prompt = """You are a reflector that condenses observation logs into their most essential form.

Your job is to:
1. Review the observation log
2. Merge related entries
3. Extract key patterns and trends
4. Retain only critical information (🚨 and ⚠️ entries)
5. Summarize informational entries (ℹ️) very briefly or omit if not essential
6. Produce a compact but informative summary

Format your output using the same emoji-based structure, but much more concise.
Focus on what future decisions need to know, not everything that happened.
"""

            # Use LLM to condense observations
            try:
                condensed = await self.orchestrator.llm.chat(
                    messages=[
                        {"role": "system", "content": reflector_system_prompt},
                        {"role": "user", "content": f"Condense these observations:\n\n{observations}"},
                    ],
                    temperature=0.2,
                )

                state["observations"] = condensed
                logger.info(f"Reflector node: Condensed observations (reduced from {len(observations)} to {len(condensed)} chars)")

            except Exception as e:
                logger.error(f"Reflector node LLM condensation failed: {e}")
                # Fallback: simple truncation (not ideal but safe)
                state["observations"] = observations[:20000] + "\n\n... [Observations truncated]"

        except Exception as e:
            logger.error(f"Reflector node failed: {e}")
            # Don't fail the workflow - just log and continue

        return state

    def _count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        This is a rough approximation (4 chars ≈ 1 token for English text).
        For production, consider using tiktoken or a proper tokenizer.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def _should_execute_skills(self, state: AgentState) -> str:
        """
        Determine if we should execute skills or respond directly.

        Returns:
            "execute" if there are skills to execute
            "no_skills" if no skills are in the action plan
            "summarize" if all skills have been executed
        """
        # If there's an error, go to no_skills_response
        if state.get("error"):
            return "no_skills"

        action_plan = state.get("action_plan", [])
        current_step = state.get("current_step", 0)

        if not action_plan:
            return "no_skills"

        if current_step >= len(action_plan):
            return "summarize"

        return "execute"

    def _should_continue_execution(self, state: AgentState) -> str:
        """
        Determine if we should continue executing skills or summarize.

        Returns:
            "continue" if there are more skills to execute
            "summarize" if all skills have been executed
        """
        action_plan = state.get("action_plan", [])
        current_step = state.get("current_step", 0)

        if current_step >= len(action_plan):
            return "summarize"

        return "continue"

    def _route_after_skill_execution(self, state: AgentState) -> str:
        """
        Route after skill execution, checking OM thresholds.

        Called after the Skill Execution Agent finishes a task.

        Returns:
            "reflector" if observations need garbage collection (> 60K tokens)
            "observer" if raw_history needs compression (> 30K tokens)
            "summarize" if all skills are complete and we should respond to user
            "execute_skill" if there are more skills to execute and memory is clean
        """
        # Count tokens in raw_message_history and observations
        raw_history = state.get("raw_message_history", [])
        observations = state.get("observations", "")

        raw_tokens = sum(self._count_tokens(str(msg)) for msg in raw_history)
        obs_tokens = self._count_tokens(observations)

        logger.debug(f"Token counts - raw_history: {raw_tokens}, observations: {obs_tokens}")

        # Check if we need to garbage collect the long-term memory
        if obs_tokens > 60_000:
            logger.info(f"Observations too large ({obs_tokens} tokens), routing to reflector")
            return "reflector"

        # Check if we need to condense recent skill outputs
        elif raw_tokens > 30_000:
            logger.info(f"Raw history too large ({raw_tokens} tokens), routing to observer")
            return "observer"

        # If memory is clean, check the action plan
        action_plan = state.get("action_plan", [])
        current_step = state.get("current_step", 0)

        if current_step >= len(action_plan):
            # Action plan complete, summarize results
            logger.info("All skills executed, routing to summarize")
            return "summarize"

        # More skills to execute
        return "execute_skill"

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
            user_message=input_data,
            observations="",
            raw_message_history=[],
            user_intent="",
            action_plan=[],
            next_skill=None,
            skill_results=[],
            current_step=0,
            final_response=None,
            error=None,
        )

        # Add user message to raw_message_history for OM tracking
        initial_state["raw_message_history"] = [f"[User Message]\n{input_data}"]

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
                "result": final_state.get("final_response"),
                "error": final_state.get("error"),
                "user_intent": final_state.get("user_intent"),
                "action_plan": final_state.get("action_plan"),
                "skill_results": final_state.get("skill_results", []),
            }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {
                "result": None,
                "error": str(e),
                "user_intent": "",
                "action_plan": [],
                "skill_results": [],
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
        await self.orchestrator.shutdown()
        await self.skill_executor.shutdown()
        await self.storage.disconnect()
        logger.info("Agent shutdown complete")
