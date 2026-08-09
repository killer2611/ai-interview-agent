"""LLM Provider — thin abstraction over OpenAI-compatible SDK.

Handles:
- API calls with retry and timeout
- Structured JSON output parsing via Pydantic
- Error handling and fallback support
- Configuration from settings
"""

from __future__ import annotations

import json
import logging
import time
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(Exception):
    """Raised when an LLM provider operation fails."""
    pass


class LLMProvider:
    """Wrapper around OpenAI-compatible API."""

    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=settings.openai_api_key or "dummy-key-for-phase1",
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        self._model = settings.llm_model
        self._max_retries = settings.llm_max_retries

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        """Generate text from LLM with retry logic."""
        if not settings.openai_api_key or settings.openai_api_key.startswith("dummy"):
            raise LLMProviderError("No valid OPENAI_API_KEY configured (offline/test mode)")

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("LLM returned empty content")
                return content.strip()

            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    str(e),
                )
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)

        raise LLMProviderError(
            f"LLM call failed after {self._max_retries + 1} attempts: {last_error}"
        )

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> T:
        """Generate structured response validated against a Pydantic model."""
        if not settings.openai_api_key or settings.openai_api_key.startswith("dummy"):
            raise LLMProviderError("No valid OPENAI_API_KEY configured (offline/test mode)")

        json_instruction = (
            "\n\nYou MUST respond with ONLY a valid JSON object matching this schema. "
            "Do not include any markdown text outside the JSON.\n"
            f"Schema: {response_model.model_json_schema()}"
        )

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                raw_text = self.generate_text(
                    system_prompt=system_prompt + json_instruction,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                json_text = self._extract_json(raw_text)
                data = json.loads(json_text)
                return response_model.model_validate(data)

            except Exception as e:
                last_error = e
                logger.warning(
                    "Structured generation failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    str(e),
                )
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)

        raise LLMProviderError(
            f"Structured generation failed after {self._max_retries + 1} attempts: {last_error}"
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON string from text, removing markdown code fences if present."""
        text = text.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip().startswith("```"):
                    end = i
                    break
            text = "\n".join(lines[start:end]).strip()

        return text
