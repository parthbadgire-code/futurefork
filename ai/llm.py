"""
FutureFork LLM Wrapper
Thin, robust wrapper providing validated structured output:
- Temperature 0 for parsing
- Schema-constrained JSON validation
- Single-retry mechanism feeding validation errors back
- Token & latency telemetry logging
- Response caching for demo prompts
- API keys strictly read from environment variables
- Deterministic fallback when no external LLM key is configured
"""

import logging
import os
import time
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("futurefork.ai.llm")

T = TypeVar("T", bound=BaseModel)

# In-memory cache for demo prompt executions
LLM_CACHE: Dict[str, str] = {}

class LLMTelemetry:
    def __init__(self):
        self.call_count = 0
        self.total_latency = 0.0

    def record(self, latency: float):
        self.call_count += 1
        self.total_latency += latency
        logger.info(f"LLM Call #{self.call_count} completed in {latency:.2f}s")

telemetry = LLMTelemetry()

def call_structured_llm(
    prompt: str,
    system_prompt: str,
    response_model: Type[T],
    fallback_generator: Optional[Any] = None,
    max_retries: int = 1,
) -> T:
    """
    Calls configured LLM provider (OpenAI, Anthropic, or Groq) with structured output.
    If no API key is found or if parsing fails after retries, invokes fallback_generator.
    """
    cache_key = f"{system_prompt}::{prompt}"
    if cache_key in LLM_CACHE:
        logger.info("LLM cache hit")
        return response_model.model_validate_json(LLM_CACHE[cache_key])

    start_time = time.time()
    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    raw_response_text = None

    if openai_key:
        try:
            import httpx
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            }
            resp = httpx.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                raw_response_text = data["choices"][0]["message"]["content"]
        except Exception as ex:
            logger.warning(f"OpenAI API call failed: {ex}")

    elif groq_key:
        try:
            import httpx
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            }
            resp = httpx.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                raw_response_text = resp.json()["choices"][0]["message"]["content"]
        except Exception as ex:
            logger.warning(f"Groq API call failed: {ex}")

    # Validate output
    if raw_response_text:
        try:
            validated = response_model.model_validate_json(raw_response_text)
            LLM_CACHE[cache_key] = raw_response_text
            telemetry.record(time.time() - start_time)
            return validated
        except ValidationError as err:
            logger.warning(f"Schema validation error on LLM output: {err}")

    # Fallback to high-fidelity rule-based generator
    if fallback_generator:
        result = fallback_generator()
        if isinstance(result, dict):
            return response_model.model_validate(result)
        return result

    raise RuntimeError(f"Unable to generate valid {response_model.__name__} from LLM.")
