"""Skill execution agent for executing individual skills."""

import json
from typing import Dict, Any, Optional
from loguru import logger
from .llm import SecureLLM
from .storage import SecureStorage
from .tools import execute_tool, shell_tool, perplexity_search


class SkillExecutionAgent:
    """
    Skill execution agent that:
    1. Uses the skill name from state variable (next skill to execute)
    2. Retrieves the full skill markdown from Redis
    3. Injects the markdown into its system prompt
    4. Takes the state variable as input
    5. Executes the skill using available tools (perplexity_search, shell_command)
    """

    SKILL_EXECUTION_SYSTEM_PROMPT = """You are a skill execution agent. Your job is to execute the following skill based on the user's request.

{observations_prefix}

{skill_markdown}

Available Tools:
You have access to the following tools to help you execute the skill:

1. perplexity_search(query: str) - Search the web using Perplexity API. Use this when you need up-to-date information, facts, or research from the internet.

2. shell_command(command: str, timeout: int = 30) - Execute a shell command safely. Use this when you need to run commands on the system.

IMPORTANT:
- Always explain what you're going to do before executing a tool
- Execute tools one at a time and analyze results before proceeding
- Provide clear, helpful feedback based on the tool outputs
- If a tool fails, explain what happened and try an alternative approach if possible
- Follow the step-by-step instructions provided in the skill above
- Respect all constraints and quality checks specified in the skill

User's Original Request:
{user_message}

Previous Execution Results:
{previous_results}

Context:
{context}

Execute the skill and provide the result. Your response will be used to answer the user's original request.
"""

    def __init__(self):
        self.llm = SecureLLM()
        self.storage = SecureStorage()

    async def initialize(self):
        """Initialize the skill execution agent."""
        await self.storage.connect()
        logger.info("Skill execution agent initialized")

    async def execute_skill(
        self,
        skill_name: str,
        user_message: str,
        previous_results: list[Dict[str, Any]] = None,
        context: Dict[str, Any] = None,
        observations: str = ""
    ) -> Dict[str, Any]:
        """
        Execute a skill by name.

        Args:
            skill_name: Name of the skill to execute
            user_message: Original user message
            previous_results: Results from previous skill executions
            context: Additional context for execution

        Returns:
            Dict with 'output' and 'error' fields
        """
        # Retrieve skill markdown from Redis
        skill_markdown = await self.storage.get_skill(skill_name)

        if not skill_markdown:
            error_msg = f"Skill '{skill_name}' not found"
            logger.error(error_msg)
            return {"error": error_msg, "output": None}

        logger.info(f"Executing skill: {skill_name}")

        # Format previous results
        previous_results_text = ""
        if previous_results:
            for i, result in enumerate(previous_results, 1):
                prev_skill = result.get('skill_name', f'Step {i}')
                prev_output = result.get('output', '')
                prev_error = result.get('error')
                previous_results_text += f"\n{prev_skill}:\n"
                if prev_error:
                    previous_results_text += f"Error: {prev_error}\n"
                else:
                    previous_results_text += f"{prev_output}\n"
        else:
            previous_results_text = "No previous results."

        # Format context
        context_text = ""
        if context:
            context_text = json.dumps(context, indent=2)
        else:
            context_text = "No additional context."

        # Build observations prefix if provided
        observations_prefix = ""
        if observations:
            observations_prefix = f"""Session Context (Previous Observations):
{observations}

---"""

        # Build system prompt with observations and full skill markdown
        system_prompt = self.SKILL_EXECUTION_SYSTEM_PROMPT.format(
            observations_prefix=observations_prefix,
            skill_markdown=skill_markdown,
            user_message=user_message,
            previous_results=previous_results_text,
            context=context_text
        )

        # Execute the skill using LLM with tool-calling capability
        try:
            # For now, use a simple chat approach without actual tool binding
            # The agent will output instructions that need to be parsed and executed
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
            )

            # Check if the response contains tool calls
            # Simple pattern matching for "perplexity_search" and "shell_command"
            output = response

            # Try to parse and execute any tool calls mentioned in the response
            tool_outputs = []
            if "perplexity_search(" in response:
                # Extract query from perplexity_search call
                import re
                match = re.search(r'perplexity_search\(["\'](.*?)["\']\)', response)
                if match:
                    query = match.group(1)
                    logger.info(f"Detected perplexity_search call with query: {query}")
                    search_result = await execute_tool("perplexity_search", query=query)
                    tool_outputs.append(f"\n\n[Perplexity Search Result]\n{search_result}")
                    output += "".join(tool_outputs)

            if "shell_command(" in response:
                # Extract command from shell_command call
                import re
                match = re.search(r'shell_command\(["\'](.*?)["\'](?:,\s*(\d+))?\)', response)
                if match:
                    command = match.group(1)
                    timeout = int(match.group(2)) if match.group(2) else 30
                    logger.info(f"Detected shell_command call: {command}")
                    shell_result = await execute_tool("shell_command", command=command, timeout=timeout)
                    tool_outputs.append(f"\n\n[Shell Command Result]\n{shell_result}")
                    output += "".join(tool_outputs)

            logger.info(f"Skill '{skill_name}' executed successfully")

            return {
                "output": output,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Failed to execute skill '{skill_name}': {e}")
            return {
                "output": None,
                "error": str(e),
            }

    async def shutdown(self):
        """Shutdown the skill execution agent."""
        await self.llm.close()
        await self.storage.disconnect()
        logger.info("Skill execution agent shutdown complete")
