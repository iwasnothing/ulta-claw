"""FastAPI backend for Secure Agent Health Check UI."""

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import redis.asyncio as redis
from cli.health import HealthChecker

# Initialize FastAPI
app = FastAPI(
    title="Secure Agent Health Check API",
    description="REST API for monitoring Secure Agent system health",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global config - Docker service names
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_USERNAME = os.getenv("REDIS_USER", None)
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
LITELM_URL = os.getenv("LITELM_URL", "http://litellm:4000")
SQUID_HOST = os.getenv("SQUID_HOST", "squid")
SQUID_PORT = int(os.getenv("SQUID_PORT", "3128"))


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Secure Agent Health Check API", "version": "1.0.0"}


@app.get("/api/health")
async def get_health() -> dict[str, Any]:
    """
    Get system health status.

    Returns comprehensive health check results for all components.
    """
    checker = HealthChecker(
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT,
        redis_password=REDIS_PASSWORD or None,
        redis_username=REDIS_USERNAME,
        gateway_url=GATEWAY_URL,
        litellm_url=LITELM_URL,
        squid_host=SQUID_HOST,
        squid_port=SQUID_PORT,
    )
    result = await checker.check_all()
    return result


@app.get("/api/health/verbose")
async def get_health_verbose() -> dict[str, Any]:
    """
    Get detailed system health status.

    Returns verbose health check results including all details.
    """
    result = await get_health()
    # Already includes details from the health check
    return result


@app.get("/api/components")
async def get_components() -> dict[str, list[str]]:
    """Get list of all health check components."""
    return {
        "components": [
            "gateway",
            "adaptor_channel",
            "agent",
            "redis",
            "litellm",
            "squid",
            "connections",
        ]
    }


@app.get("/api/config")
async def get_config() -> dict[str, str | int]:
    """Get current health check configuration."""
    return {
        "redis_host": REDIS_HOST,
        "redis_port": REDIS_PORT,
        "gateway_url": GATEWAY_URL,
        "litellm_url": LITELM_URL,
        "squid_host": SQUID_HOST,
        "squid_port": SQUID_PORT,
    }


# Skill Management Models
class SkillCreate(BaseModel):
    """Model for creating a new skill."""
    name: str
    description: str
    condition: str
    instructions: str
    resources: str = ""


def _parse_skill_markdown(skill_name: str, skill_markdown: str) -> dict:
    """Parse skill markdown to extract name, description, and condition."""
    import re

    description_match = re.search(r'##?\s*What.*Skill\s*Does?\s*\n(.*?)(?=##|\n\n|\Z)', skill_markdown, re.IGNORECASE | re.DOTALL)
    condition_match = re.search(r'##?\s*When.*Should\s*Be\s*Used\s*\n(.*?)(?=##|\n\n|\Z)', skill_markdown, re.IGNORECASE | re.DOTALL)

    description = description_match.group(1).strip() if description_match else ""
    condition = condition_match.group(1).strip() if condition_match else ""

    return {
        "name": skill_name,
        "description": description,
        "condition": condition,
    }


# Skill Management Endpoints
async def get_redis_client() -> redis.Redis:
    """Get a Redis client connection."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )


@app.get("/api/skills")
async def get_skills() -> dict[str, Any]:
    """
    Get all skills from Redis.

    Returns a dictionary of skill names to skill data.
    """
    try:
        r = await get_redis_client()
        skill_names = await r.smembers("skills:index")
        skills = {}

        for skill_name in skill_names:
            skill_key = f"skill:{skill_name}"
            skill_markdown = await r.get(skill_key)
            if skill_markdown:
                # Parse markdown to extract name, description, condition
                skills[skill_name] = _parse_skill_markdown(skill_name, skill_markdown)

        await r.close()
        return {"skills": skills}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skills/catalog")
async def get_skill_catalog() -> dict[str, Any]:
    """
    Get skill catalog (name, description, and condition to use only).
    """
    try:
        r = await get_redis_client()
        skill_names = await r.smembers("skills:index")
        catalog = {}

        for skill_name in skill_names:
            skill_key = f"skill:{skill_name}"
            skill_markdown = await r.get(skill_key)
            if skill_markdown:
                # Parse markdown to extract name, description, condition
                parsed = _parse_skill_markdown(skill_name, skill_markdown)
                catalog[skill_name] = {
                    "name": parsed["name"],
                    "description": parsed["description"],
                    "condition": parsed["condition"],
                }

        await r.close()
        return {"catalog": catalog}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/skills")
async def create_skill(skill: SkillCreate) -> dict[str, Any]:
    """
    Create a new skill in Redis.

    Stores the skill as a markdown string with all sections.
    """
    try:
        r = await get_redis_client()

        # Check if skill already exists
        skill_key = f"skill:{skill.name}"
        if await r.exists(skill_key):
            await r.close()
            raise HTTPException(status_code=400, detail=f"Skill '{skill.name}' already exists")

        # Combine fields into markdown format
        skill_markdown = f"""# {skill.name}

## What This Skill Does

{skill.description}

## When This Should Be Used

{skill.condition}

## Instructions

{skill.instructions}

"""

        # Add optional resources section if provided
        if skill.resources and skill.resources.strip():
            skill_markdown += f"""## Supporting Resources

{skill.resources}
"""

        # Store skill markdown
        await r.set(skill_key, skill_markdown)

        # Add to index
        await r.sadd("skills:index", skill.name)

        await r.close()
        return {"success": True, "message": f"Skill '{skill.name}' created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skills/{skill_name}")
async def get_skill(skill_name: str) -> dict[str, Any]:
    """
    Get a specific skill by name.

    Returns the full markdown string for the skill.
    """
    try:
        r = await get_redis_client()
        skill_key = f"skill:{skill_name}"
        skill_markdown = await r.get(skill_key)

        if not skill_markdown:
            await r.close()
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        # Parse markdown to return structured data for UI
        parsed = _parse_skill_markdown(skill_name, skill_markdown)

        await r.close()
        return {
            "name": parsed["name"],
            "description": parsed["description"],
            "condition": parsed["condition"],
            "full_markdown": skill_markdown,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/skills/{skill_name}")
async def delete_skill(skill_name: str) -> dict[str, Any]:
    """
    Delete a skill by name.
    """
    try:
        r = await get_redis_client()
        skill_key = f"skill:{skill_name}"

        # Check if skill exists
        if not await r.exists(skill_key):
            await r.close()
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        # Delete skill
        await r.delete(skill_key)

        # Remove from index
        await r.srem("skills:index", skill_name)

        await r.close()
        return {"success": True, "message": f"Skill '{skill_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
