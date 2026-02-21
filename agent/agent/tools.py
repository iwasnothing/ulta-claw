"""Function tools for skill execution agent."""

import os
import asyncio
import httpx
from typing import Dict, Any, Optional
from loguru import logger
from langchain_core.tools import tool


@tool
async def perplexity_search(query: str) -> str:
    """
    Search the web using Perplexity API.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    api_key = os.getenv("PERPLEXITY_API_KEY")
    api_url = os.getenv("PERPLEXITY_API_URL", "https://api.perplexity.ai")

    if not api_key:
        return "Error: PERPLEXITY_API_KEY environment variable not set"

    logger.info(f"Performing Perplexity search: {query[:100]}...")

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        ) as client:
            response = await client.post(
                f"{api_url}/chat/completions",
                json={
                    "model": "sonar-medium-online",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful search assistant. Provide accurate, concise search results."
                        },
                        {
                            "role": "user",
                            "content": f"Search for: {query}"
                        }
                    ],
                    "max_tokens": 2048,
                }
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"Perplexity search completed, got {len(content)} chars")
            return content

    except httpx.TimeoutException:
        logger.error("Perplexity search timed out")
        return "Error: Search request timed out"
    except httpx.HTTPStatusError as e:
        logger.error(f"Perplexity API error: {e.response.status_code}")
        return f"Error: Perplexity API returned status {e.response.status_code}"
    except Exception as e:
        logger.error(f"Perplexity search failed: {e}")
        return f"Error: {str(e)}"


async def shell_command(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command safely.

    Args:
        command: The shell command to execute
        timeout: Timeout in seconds (default: 30)

    Returns:
        Command output as a string
    """
    logger.info(f"Executing shell command: {command[:100]}...")

    # Security: Basic command validation
    dangerous_commands = ["rm -rf /", "dd if=", ":(){ :|:& };:", "mkfs", "format"]
    if any(dangerous in command.lower() for dangerous in dangerous_commands):
        logger.warning(f"Blocked potentially dangerous command: {command}")
        return "Error: Command blocked for security reasons"

    try:
        # Execute command
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout
        )

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        output = ""
        if stdout_str:
            output += f"STDOUT:\n{stdout_str}\n"
        if stderr_str:
            output += f"STDERR:\n{stderr_str}\n"
        output += f"Exit code: {proc.returncode}"

        logger.info(f"Shell command completed with exit code {proc.returncode}")
        return output

    except asyncio.TimeoutError:
        logger.error(f"Shell command timed out after {timeout}s")
        proc.kill()
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        logger.error(f"Shell command failed: {e}")
        return f"Error: {str(e)}"


# Create shell command tool with type hints
shell_tool = {
    "name": "shell_command",
    "description": "Execute a shell command safely. Returns stdout, stderr, and exit code.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30)",
                "default": 30
            }
        },
        "required": ["command"]
    }
}


def get_available_tools() -> Dict[str, Any]:
    """Get all available function tools."""
    return {
        "perplexity_search": perplexity_search,
        "shell_command": shell_command,
    }


async def execute_tool(tool_name: str, **kwargs) -> str:
    """
    Execute a tool by name.

    Args:
        tool_name: Name of the tool to execute
        **kwargs: Tool arguments

    Returns:
        Tool execution result
    """
    tools = get_available_tools()

    if tool_name not in tools:
        return f"Error: Unknown tool '{tool_name}'"

    tool_func = tools[tool_name]

    try:
        if tool_name == "shell_command":
            return await shell_command(**kwargs)
        elif tool_name == "perplexity_search":
            result = await perplexity_search(kwargs.get("query", ""))
            return result
        else:
            return await tool_func(**kwargs)
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return f"Error: {str(e)}"
