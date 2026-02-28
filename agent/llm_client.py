"""RouterAI API client — singleton AsyncOpenAI with retry logic.

Provides chat completion (text/JSON), embeddings, and batch embeddings
through a unified interface pointing to https://routerai.ru/api/v1.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Return (or lazily create) the singleton AsyncOpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.routerai_api_key,
            base_url=settings.routerai_base_url,
        )
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    **kwargs: Any,
):
    """Send a chat completion request with retry + fallback logic."""
    client = get_client()
    model = model or settings.llm_model
    try:
        return await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=kwargs.pop("temperature", settings.llm_temperature),
            max_tokens=kwargs.pop("max_tokens", settings.llm_max_tokens),
            **kwargs,
        )
    except Exception as exc:
        if model != settings.llm_fallback_model:
            logger.warning(
                "Primary model %s failed (%s), falling back to %s",
                model, exc, settings.llm_fallback_model,
            )
            return await client.chat.completions.create(
                model=settings.llm_fallback_model,
                messages=messages,
                temperature=kwargs.pop("temperature", settings.llm_temperature),
                max_tokens=kwargs.pop("max_tokens", settings.llm_max_tokens),
                **kwargs,
            )
        raise


async def chat_completion_json(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> dict:
    """Chat completion that forces JSON output and parses the result."""
    response = await chat_completion(
        messages,
        model=model,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Retry once with a hint
        logger.warning("Invalid JSON from LLM, retrying with hint: %s", raw[:200])
        messages_retry = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "Ответ невалидный JSON. Верни только валидный JSON без пояснений."},
        ]
        response = await chat_completion(
            messages_retry,
            model=model,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)


async def embed_text(text: str) -> list[float]:
    """Embed a single text string → 1024-dim vector."""
    client = get_client()
    resp = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return resp.data[0].embedding


async def embed_batch(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Embed multiple texts in batches → list of 1024-dim vectors."""
    client = get_client()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = await client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
        )
        all_embeddings.extend([d.embedding for d in resp.data])
    return all_embeddings
