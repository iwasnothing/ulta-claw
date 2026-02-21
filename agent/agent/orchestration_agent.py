"""Orchestration agent for managing skill execution workflow."""

import json
from typing import Dict, Any, Optional, List
from loguru import logger
from .llm import SecureLLM
from .storage import SecureStorage


class OrchestrationState(dict):
    """State for orchestration workflow."""

    user_message: str
    user_intent: str = ""
    action_plan: List[str] = []
    next_skill: Optional[str] = None
    execution_results: List[Dict[str, Any]] = []
    current_step: int = 0
    final_response: Optional[str] = None
    error: Optional[str] = None


class OrchestrationAgent:
    """
    Orchestration agent that:
    1. Queries all skills from Redis
    2. Extracts skill catalog (name, description, condition to use)
    3. Determines user intent from user message
    4. Generates action plan (list of skills to use)
    5. Routes to skill execution agent
    6. Summarizes results and responds to user
    """

    ORCHESTRATION_SYSTEM_PROMPT = """You are an intelligent orchestration agent that coordinates skill execution to fulfill user requests.

{observations_prefix}

You have access to a catalog of available skills. Your job is to:

1. Analyze the user's message to understand their intent
2. Determine which skills (if any) can fulfill the user's intent
3. Create an action plan listing the skills needed
4. If no skills can fulfill the intent, respond with a clear message

When analyzing the user's request:
- Consider what the user is asking for
- Match it against available skills based on their descriptions and conditions
- Think about the sequence of operations needed
- If multiple skills are needed, order them logically

Your response must be in JSON format with these fields:
{{
  "user_intent": "brief description of what the user wants",
  "action_plan": ["skill_name1", "skill_name2", ...],
  "reasoning": "brief explanation of your decision"
}}

If no skills can fulfill the user's intent:
- Set "action_plan" to an empty list []
- Explain in "reasoning" that the required skills are not available
- The system will respond to the user with: "I have not equipped with required skills to fulfill your intent"

Available Skills:
{skill_catalog}
"""

    SUMMARY_SYSTEM_PROMPT = """You are an intelligent assistant that summarizes skill execution results and provides a helpful response to the user.

You have been given:
1. The original user message
2. The action plan that was executed
3. The results from each skill execution

Your job is to:
1. Review all the execution results
2. Synthesize the information into a coherent response
3. Answer the user's question or acknowledge the completion of their request
4. Present the information in a clear, user-friendly way

Be helpful and informative. Use markdown formatting for better readability.
If there were any errors during execution, acknowledge them and explain what happened.
"""

    def __init__(self):
        self.llm = SecureLLM()
        self.storage = SecureStorage()

    async def initialize(self):
        """Initialize the orchestration agent."""
        await self.storage.connect()
        logger.info("Orchestration agent initialized")

    async def determine_action_plan(
        self, user_message: str, observations: str = ""
    ) -> OrchestrationState:
        """
        Determine the action plan based on user message.

        Args:
            user_message: The user's input message

        Returns:
            Orchestration state with user intent and action plan
        """
        # Get skill catalog
        skill_catalog = await self.storage.get_skill_catalog()
        logger.info(f"=== SKILL CATALOG START ===\n{skill_catalog}\n=== SKILL CATALOG END ===")

        # Build observations prefix if provided
        observations_prefix = ""
        if observations:
            observations_prefix = f"""Session Context (Previous Observations):
{observations}

---"""

        # Build system prompt with observations and skill catalog
        system_prompt = self.ORCHESTRATION_SYSTEM_PROMPT.format(
            observations_prefix=observations_prefix,
            skill_catalog=skill_catalog
        )

        # Call LLM to determine action plan
        try:
            logger.debug(f"Orchestration system prompt:\n{system_prompt}")
            logger.debug(f"User message for orchestration: {user_message}")

            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
            )

            logger.debug(f"Raw LLM response for orchestration:\n{response}")

            # Strip markdown code fences if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first line (```json or ```) and last line (```)
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines).strip()
                logger.debug(f"Stripped markdown fences, cleaned response:\n{cleaned}")

            # Parse JSON response
            try:
                result = json.loads(cleaned)
                logger.debug(f"Parsed orchestration result: {result}")

                state = OrchestrationState(
                    user_message=user_message,
                    user_intent=result.get("user_intent", ""),
                    action_plan=result.get("action_plan", []),
                    current_step=0,
                    execution_results=[],
                )

                logger.info(
                    f"Determined action plan: {state['action_plan']} "
                    f"for intent: {state['user_intent']}"
                )

                return state

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse orchestration response: {e}")
                logger.error(f"Response that failed parsing:\n{response}")

                state = OrchestrationState(
                    user_message=user_message,
                    user_intent="Unable to determine",
                    action_plan=[],
                    current_step=0,
                    execution_results=[],
                )
                return state

        except Exception as e:
            logger.error(f"Failed to determine action plan: {e}", exc_info=True)
            state = OrchestrationState(
                user_message=user_message,
                user_intent="Error",
                action_plan=[],
                error=str(e),
            )
            return state

    async def summarize_results(
        self, state: OrchestrationState
    ) -> str:
        """
        Summarize execution results and generate final response.

        Args:
            state: Current orchestration state with execution results

        Returns:
            Final response to the user
        """
        # Build summary prompt
        summary_prompt = f"""Original User Message: {state['user_message']}

Action Plan:
{', '.join(state['action_plan']) if state['action_plan'] else 'No skills executed'}

Execution Results:
"""

        for i, result in enumerate(state['execution_results'], 1):
            skill_name = result.get('skill_name', f'Step {i}')
            output = result.get('output', '')
            error = result.get('error')

            summary_prompt += f"\n{skill_name}:\n"
            if error:
                summary_prompt += f"Error: {error}\n"
            else:
                summary_prompt += f"{output}\n"

        try:
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": self.SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": summary_prompt},
                ],
                temperature=0.7,
            )

            logger.info("Generated summary response")
            return response

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return f"I encountered an error while processing your request: {str(e)}"

    async def should_use_skills(self, state: OrchestrationState) -> bool:
        """
        Check if there are skills to execute.

        Args:
            state: Current orchestration state

        Returns:
            True if there are skills in the action plan
        """
        return len(state.get('action_plan', [])) > 0

    async def get_next_skill(self, state: Dict[str, Any]) -> Optional[str]:
        """
        Get the next skill to execute.

        Args:
            state: Current state dictionary

        Returns:
            Next skill name or None if no more skills
        """
        action_plan = state.get('action_plan', [])
        current_step = state.get('current_step', 0)

        if current_step >= len(action_plan):
            return None

        return action_plan[current_step]

    async def advance_step(self, state: Dict[str, Any]):
        """
        Advance to the next step in the action plan.

        Args:
            state: State dictionary to update
        """
        current_step = state.get('current_step', 0)
        state['current_step'] = current_step + 1
        state['next_skill'] = await self.get_next_skill(state)

    async def record_execution_result(
        self, state: Dict[str, Any], skill_name: str, output: str, error: Optional[str] = None
    ):
        """
        Record the result of a skill execution.

        Args:
            state: State dictionary to update
            skill_name: Name of the executed skill
            output: Output from the skill
            error: Optional error message
        """
        result = {
            'skill_name': skill_name,
            'output': output,
            'error': error,
        }
        state['execution_results'].append(result)
        logger.info(f"Recorded execution result for {skill_name}")

    async def is_plan_complete(self, state: OrchestrationState) -> bool:
        """
        Check if the action plan is complete.

        Args:
            state: Current orchestration state

        Returns:
            True if all skills have been executed
        """
        action_plan = state.get('action_plan', [])
        current_step = state.get('current_step', 0)
        return current_step >= len(action_plan)

    async def shutdown(self):
        """Shutdown the orchestration agent."""
        await self.llm.close()
        await self.storage.disconnect()
        logger.info("Orchestration agent shutdown complete")
