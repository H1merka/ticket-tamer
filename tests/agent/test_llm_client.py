"""Tests for agent/llm_client.py — RouterAI API client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.llm_client import chat_completion, chat_completion_json, embed_text, embed_batch, get_client


# ---------------------------------------------------------------------------
# get_client — singleton
# ---------------------------------------------------------------------------


def test_get_client_returns_same_instance():
    """get_client() returns the same AsyncOpenAI singleton."""
    import agent.llm_client as mod
    mod._client = None  # reset
    c1 = get_client()
    c2 = get_client()
    assert c1 is c2
    mod._client = None  # cleanup


# ---------------------------------------------------------------------------
# chat_completion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completion_success():
    mock_response = MagicMock()
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("agent.llm_client.get_client", return_value=mock_client):
        result = await chat_completion([{"role": "user", "content": "Hello"}])

    assert result is mock_response
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_chat_completion_fallback_on_failure():
    """If primary model fails, falls back to llm_fallback_model."""
    mock_fallback_response = MagicMock()
    mock_client = AsyncMock()

    call_count = 0

    async def _mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if kwargs.get("model") != "qwen/qwen3.5-flash-02-23":
            raise RuntimeError("Primary model down")
        return mock_fallback_response

    mock_client.chat.completions.create = _mock_create

    with (
        patch("agent.llm_client.get_client", return_value=mock_client),
        patch("agent.llm_client.settings", MagicMock(
            llm_model="deepseek/deepseek-v3.2",
            llm_fallback_model="qwen/qwen3.5-flash-02-23",
            llm_temperature=0.1,
            llm_max_tokens=2048,
        )),
    ):
        # Disable tenacity retries for this test
        from agent.llm_client import chat_completion
        result = await chat_completion.__wrapped__(
            [{"role": "user", "content": "Hello"}],
        )

    assert result is mock_fallback_response


# ---------------------------------------------------------------------------
# chat_completion_json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completion_json_parses_response():
    mock_choice = MagicMock()
    mock_choice.message.content = '{"key": "value"}'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("agent.llm_client.chat_completion", new_callable=AsyncMock, return_value=mock_response):
        result = await chat_completion_json([{"role": "user", "content": "test"}])

    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_chat_completion_json_retries_on_invalid_json():
    """Invalid JSON → retries with hint → parses retry result."""
    mock_bad_choice = MagicMock()
    mock_bad_choice.message.content = "not json"
    mock_bad_response = MagicMock()
    mock_bad_response.choices = [mock_bad_choice]

    mock_good_choice = MagicMock()
    mock_good_choice.message.content = '{"fixed": true}'
    mock_good_response = MagicMock()
    mock_good_response.choices = [mock_good_choice]

    with patch(
        "agent.llm_client.chat_completion",
        new_callable=AsyncMock,
        side_effect=[mock_bad_response, mock_good_response],
    ):
        result = await chat_completion_json([{"role": "user", "content": "test"}])

    assert result == {"fixed": True}


# ---------------------------------------------------------------------------
# embed_text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_text_returns_vector():
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1] * 1024
    mock_response = MagicMock()
    mock_response.data = [mock_embedding]
    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    with patch("agent.llm_client.get_client", return_value=mock_client):
        result = await embed_text("test text")

    assert len(result) == 1024
    assert result[0] == 0.1


# ---------------------------------------------------------------------------
# embed_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_batch_returns_vectors():
    mock_emb1 = MagicMock()
    mock_emb1.embedding = [0.1] * 1024
    mock_emb2 = MagicMock()
    mock_emb2.embedding = [0.2] * 1024
    mock_response = MagicMock()
    mock_response.data = [mock_emb1, mock_emb2]
    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    with patch("agent.llm_client.get_client", return_value=mock_client):
        result = await embed_batch(["text1", "text2"], batch_size=100)

    assert len(result) == 2
    assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_embed_batch_handles_batching():
    """Large input is split into batches."""
    mock_emb = MagicMock()
    mock_emb.embedding = [0.1] * 1024
    mock_response = MagicMock()
    mock_response.data = [mock_emb]
    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    texts = [f"text_{i}" for i in range(5)]

    with patch("agent.llm_client.get_client", return_value=mock_client):
        result = await embed_batch(texts, batch_size=2)

    # Should have been called 3 times: 2+2+1
    assert mock_client.embeddings.create.call_count == 3
    assert len(result) == 5
