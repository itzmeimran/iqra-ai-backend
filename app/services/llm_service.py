"""
LLM Service — LangChain-based provider abstraction layer.
Supports:
- Ollama via ChatOllama
- LM Studio / vLLM / cloud via OpenAI-compatible ChatOpenAI

This version is LangSmith-traceable because model calls go through LangChain.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, List

from app.core.config import settings

logger = logging.getLogger(__name__)


def _normalize_messages(messages: List[dict]) -> List[dict]:
    normalized: List[dict] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        normalized.append({"role": role, "content": content})
    return normalized


def _get_langchain_model(model: str | None = None):
    provider = settings.llm_provider.lower()
    selected_model = model or settings.default_model
    base_url = settings.llm_base_url.rstrip("/")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=selected_model,
            base_url=base_url,
            temperature=0.7,
        )

    if provider in {"lmstudio", "vllm", "cloud"}:
        from langchain_openai import ChatOpenAI

        openai_base = f"{base_url}/v1" if not base_url.endswith("/v1") else base_url

        return ChatOpenAI(
            model=selected_model,
            base_url=openai_base,
            api_key="local-not-required",
            temperature=0.7,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")


async def get_available_models() -> list[dict]:
    provider = settings.llm_provider.lower()
    base = settings.llm_base_url.rstrip("/")

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as client:
            if provider == "ollama":
                response = await client.get(f"{base}/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
                return [
                    {
                        "id": model["name"],
                        "name": model["name"],
                        "provider": "ollama",
                        "isAvailable": True,
                        "contextLength": None,
                    }
                    for model in models
                ]

            response = await client.get(
                f"{base}/v1/models" if not base.endswith("/v1") else f"{base}/models"
            )
            response.raise_for_status()
            data = response.json().get("data", [])
            return [
                {
                    "id": model["id"],
                    "name": model["id"],
                    "provider": provider,
                    "isAvailable": True,
                    "contextLength": model.get("context_window"),
                }
                for model in data
            ]
    except Exception as exc:
        logger.warning("Could not fetch models from LLM runtime: %s", exc)
        return []


async def check_llm_health() -> dict:
    provider = settings.llm_provider.lower()
    base = settings.llm_base_url.rstrip("/")

    try:
        import httpx

        async with httpx.AsyncClient(timeout=3) as client:
            if provider == "ollama":
                response = await client.get(f"{base}/api/tags")
            else:
                response = await client.get(
                    f"{base}/v1/models" if not base.endswith("/v1") else f"{base}/models"
                )
            response.raise_for_status()

        return {
            "status": "ok",
            "provider": provider,
            "baseUrl": base,
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "provider": provider,
            "baseUrl": base,
            "error": str(exc),
        }


async def stream_chat(
    messages: List[dict],
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream text chunks through LangChain so LangSmith can trace the run.
    """
    chat_model = _get_langchain_model(model)
    normalized_messages = _normalize_messages(messages)

    try:
        async for chunk in chat_model.astream(normalized_messages):
            content = getattr(chunk, "content", "")

            if isinstance(content, str):
                if content:
                    yield content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str) and item:
                        yield item
                    elif isinstance(item, dict):
                        text = item.get("text", "")
                        if text:
                            yield text
    except Exception as exc:
        logger.exception("Streaming chat failed: %s", exc)
        raise


async def complete_chat(messages: List[dict], model: str | None = None) -> str:
    """
    Non-streaming completion through LangChain.
    """
    chat_model = _get_langchain_model(model)
    normalized_messages = _normalize_messages(messages)

    try:
        result = await chat_model.ainvoke(normalized_messages)
        content = getattr(result, "content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text", "")
                    if text:
                        parts.append(text)
            return "".join(parts)

        return ""
    except Exception as exc:
        logger.exception("Completion failed: %s", exc)
        raise