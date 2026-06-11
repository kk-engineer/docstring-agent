from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv


class LLMClient:
    """Llmclient."""
    _instance: Optional["LLMClient"] = None

    def __init__(self, config) -> None:
        """Initialise LLMClient."""
        load_dotenv()
        self.model: str = config.llm.model
        self.provider: str = config.llm.provider
        self.base_url: str = config.llm.base_url
        self.max_tokens: int = config.llm.max_tokens
        self.temperature: float = config.llm.temperature
        self.timeout_seconds: int = config.llm.timeout_seconds
        self.max_retries: int = config.llm.max_retries
        self.reachability_prompt: str = config.llm.reachability_check_prompt

        env_key = f"{self.provider}_api_key".lower()
        self.api_key: Optional[str] = os.environ.get(env_key)
        if not self.api_key:
            from .logger import Logger

            logger = Logger.get_instance()
            logger.error(f"{env_key} not found in environment")
            sys.exit(1)

    @classmethod
    def get_instance(cls, config=None) -> "LLMClient":
        """Return instance."""
        if cls._instance is None:
            if config is None:
                raise RuntimeError(
                    "LLMClient not initialized. Call LLMClient.get_instance(config) first."
                )
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset instance."""
        cls._instance = None

    def _get_litellm_params(self) -> Dict[str, Any]:
        """ get litellm params."""
        return {
            "model": f"openai/{self.model}",
            "base_url": self.base_url,
            "api_key": self.api_key,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout_seconds,
        }

    async def _acomplete(self, prompt: str, system: Optional[str] = None) -> str:
        """ acomplete."""
        import litellm

        params = self._get_litellm_params()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        params["messages"] = messages

        start = time.time()
        response = await litellm.acompletion(**params)
        latency_ms = (time.time() - start) * 1000

        from .logger import Logger

        logger = Logger.get_instance()
        usage = response.usage
        logger.debug(
            f"LLM call: prompt_tokens={usage.prompt_tokens}, "
            f"completion_tokens={usage.completion_tokens}, "
            f"latency_ms={latency_ms:.0f}"
        )

        return response.choices[0].message.content or ""

    async def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """Complete."""
        last_exception: Optional[Exception] = None
        from .logger import Logger
        logger = Logger.get_instance()
        logger.print_panel("LLM Request", prompt)
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._acomplete(prompt, system)
            except ImportError:
                raise
            except Exception as e:
                last_exception = e

                logger.warning(
                    f"LLM call attempt {attempt}/{self.max_retries} failed: {e}"
                )
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)

        from .logger import Logger

        logger = Logger.get_instance()
        logger.error(f"LLM call failed after {self.max_retries} retries: {last_exception}")
        if last_exception:
            raise last_exception
        raise RuntimeError("LLM call failed with unknown error")

    async def complete_structured(  # noqa: E501
        self, prompt: str, output_schema: Dict[str, Any],
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete structured."""
        import json

        schema_desc = "\n".join(f"  {k}: {v}" for k, v in output_schema.items())  # noqa: E501
        schema_prompt = (
            f"{prompt}\n\n"
            f"You MUST respond with valid JSON matching this schema:\n"
            f"{schema_desc}\n\nJSON:"
        )
        raw = await self.complete(schema_prompt, system)
        return json.loads(raw)

    async def check_reachability(self) -> None:
        """Check reachability."""
        from .logger import Logger

        logger = Logger.get_instance()
        logger.notice("Checking LLM reachability...")
        try:
            result = await self.complete(self.reachability_prompt)
            if result.strip():
                logger.success("LLM reachability check passed")
            else:
                logger.error("LLM reachability check returned empty response")
                sys.exit(1)
        except Exception as e:
            logger.error(f"LLM reachability check failed: {e}")
            sys.exit(1)
