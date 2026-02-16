"""Secure LLM client using LiteLLM proxy."""

from typing import Optional, Dict, Any
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import get_config


class SecureLLM:
    """Secure LLM client that routes through LiteLLM proxy."""

    def __init__(self):
        self.config = get_config()
        self.client = None
        self._initialize()

    def _initialize(self):
        """Initialize LiteLLM client with proxy."""
        try:
            from litellm import completion

            self.client = completion
            logger.info("LiteLLM client initialized")
        except ImportError as e:
            logger.error(f"Failed to import litellm: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate text using LLM through LiteLLM proxy.

        Args:
            prompt: The prompt to send to the LLM
            model: Model name (defaults to config)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        model = model or self.config.model_name
        temperature = temperature or self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        logger.debug(f"Generating with model={model}, temp={temperature}")

        try:
            response = self.client(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                api_base=self.config.litellm_endpoint,
                api_key=self.config.litellm_key,
                **kwargs
            )

            result = response.choices[0].message.content
            logger.debug(f"Generated {len(result)} characters")

            return result

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def chat(
        self,
        messages: list[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Chat with LLM through LiteLLM proxy.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (defaults to config)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated response
        """
        model = model or self.config.model_name
        temperature = temperature or self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        logger.debug(f"Chat with model={model}, {len(messages)} messages")

        try:
            response = self.client(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_base=self.config.litellm_endpoint,
                api_key=self.config.litellm_key,
                **kwargs
            )

            result = response.choices[0].message.content
            logger.debug(f"Chat response: {len(result)} characters")

            return result

        except Exception as e:
            logger.error(f"Chat failed: {e}")
            raise
