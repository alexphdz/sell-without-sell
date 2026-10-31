"""Optional selective Anthropic LLM adapter for uncertain spans.

Fully wired but disabled by default. Mock adapter for tests.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import Any

from pydantic import Field

from kipu_pay.core.logging import get_logger
from kipu_pay.core.models import KipuBaseModel

logger = get_logger(__name__)


class LLMSettings(KipuBaseModel):
    """LLM configuration (not part of main Settings to avoid startup failure)."""

    enabled: bool = Field(default=False, alias="PII_LLM_ENABLED")
    provider: str = Field(default="anthropic", alias="PII_LLM_PROVIDER")
    model: str = Field(default="claude-3-haiku-20240307", alias="PII_LLM_MODEL")
    api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    timeout_seconds: int = Field(default=15, alias="PII_LLM_TIMEOUT_SECONDS")
    max_concurrent: int = Field(default=5, alias="PII_LLM_MAX_CONCURRENT_REQUESTS")
    max_calls_per_run: int = Field(default=300, alias="PII_LLM_MAX_CALLS_PER_RUN")
    max_input_chars: int = Field(default=2500, alias="PII_LLM_MAX_INPUT_CHARS")

    class Config:
        populate_by_name = True


class LLMDetectedSpan(KipuBaseModel):
    quote: str
    category: str
    confidence: str
    action: str = "replace"
    reason: str = ""
    identity_hint: str = ""


class LLMResponse(KipuBaseModel):
    spans: list[LLMDetectedSpan] = Field(default_factory=list)
    kept: list[dict[str, str]] = Field(default_factory=list)


class LLMDetector:
    """Optional bounded LLM detector with strict validation."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or LLMSettings()
        self._call_count = 0
        self._semaphore: asyncio.Semaphore | None = None
        self._client: Any = None

    def _ensure_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.settings.max_concurrent)
        return self._semaphore

    async def detect(self, text: str, surface_path: str = "") -> list[dict[str, Any]]:
        """Return raw dict spans from LLM, validated against original text."""
        if not self.settings.enabled:
            return []
        if not self.settings.api_key:
            logger.warning("llm_disabled_no_key")
            return []
        if self._call_count >= self.settings.max_calls_per_run:
            logger.warning("llm_budget_exhausted")
            return []
        if len(text) > self.settings.max_input_chars:
            text = text[: self.settings.max_input_chars]

        self._call_count += 1
        sem = self._ensure_semaphore()

        async with sem:
            try:
                return await self._call_api(text, surface_path)
            except Exception as exc:
                logger.warning("llm_call_failed", error=str(type(exc).__name__))
                return []

    async def _call_api(self, text: str, surface_path: str) -> list[dict[str, Any]]:
        # Lazy import to avoid hard dependency
        try:
            import httpx
        except ImportError:  # pragma: no cover
            return []

        system_prompt = (
            "You are a PII detection assistant. Given a text fragment, output ONLY valid JSON "
            "with an object containing 'spans' and 'kept'. Each span has: quote (exact substring), "
            "category (person, email, phone, national_id, address, organization, place, public_figure, "
            "brand, occupation, neighborhood, birth_year, dob, plate, account, passport), "
            "confidence (strong, contextual, weak), action (replace, generalize, keep, review). "
            "Do not rewrite the text. Do not invent spans not present in the input."
        )
        user_prompt = f"Analyze this text and return JSON:\n\n{text}\n"

        headers = {
            "x-api-key": self.settings.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.settings.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        # Extract JSON from markdown code block if needed
        raw_json = content
        if "```json" in raw_json:
            raw_json = raw_json.split("```json")[1].split("```")[0]
        elif "```" in raw_json:
            raw_json = raw_json.split("```")[1].split("```")[0]

        try:
            parsed = json.loads(raw_json.strip())
        except json.JSONDecodeError as exc:
            logger.warning("llm_json_parse_failed", error=str(exc))
            return []

        spans: list[dict[str, Any]] = []
        for s in parsed.get("spans", []):
            quote = s.get("quote", "")
            if not quote:
                continue
            # Validate quote exists in original text
            if quote not in text:
                logger.warning("llm_span_not_in_text", quote_len=len(quote))
                continue
            spans.append(s)
        return spans

    def reset_budget(self) -> None:
        self._call_count = 0


class MockLLMDetector(LLMDetector):
    """Deterministic fake LLM for tests."""

    async def detect(self, text: str, surface_path: str = "") -> list[dict[str, Any]]:
        return []
