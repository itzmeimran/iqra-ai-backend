"""
LangGraph nodes — each is a pure async function that receives and returns state.
"""
from __future__ import annotations
import logging
from typing import AsyncGenerator

from app.graph.state import ChatGraphState
from app.services import chat_service, usage_service, llm_service
from app.utils.token_counter import count_tokens

logger = logging.getLogger(__name__)


# ── 1. validate_token_limit ───────────────────────────────────────────────────

async def validate_token_limit(state: ChatGraphState) -> ChatGraphState:
    estimated = count_tokens(state["user_content"])
    try:
        await usage_service.check_limits(state["user"], estimated)
    except Exception as exc:
        state["error"] = str(exc)
    state["input_tokens"] = estimated
    return state


# ── 2. load_chat_history ──────────────────────────────────────────────────────

async def load_chat_history(state: ChatGraphState) -> ChatGraphState:
    if state.get("error"):
        return state
    msgs = await chat_service.get_messages(state["user"], state["session_id"])
    # Keep last 40 messages for context window management
    state["history"] = msgs[-40:]
    return state


# ── 3. save_user_message ─────────────────────────────────────────────────────

async def save_user_message(state: ChatGraphState) -> ChatGraphState:
    if state.get("error"):
        return state
    user_id = str(state["user"]["_id"])
    msg = await chat_service.save_message(
        session_id=state["session_id"],
        user_id=user_id,
        role="user",
        content=state["user_content"],
        token_count=state["input_tokens"],
    )
    state["user_message"] = msg

    # Auto-title from first message
    await chat_service.auto_title_session(state["session_id"], user_id, state["user_content"])
    return state


# ── 4. call_llm (non-streaming) ───────────────────────────────────────────────

async def call_llm(state: ChatGraphState) -> ChatGraphState:
    if state.get("error"):
        return state

    messages = [{"role": m["role"], "content": m["content"]} for m in state["history"]]
    messages.append({"role": "user", "content": state["user_content"]})

    try:
        response = await llm_service.complete_chat(messages, model=state.get("model"))
        state["response_content"] = response
        state["output_tokens"] = count_tokens(response)
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        state["error"] = f"LLM error: {exc}"
        state["response_content"] = ""
        state["output_tokens"] = 0

    return state


# ── 5. save_assistant_message ─────────────────────────────────────────────────

async def save_assistant_message(state: ChatGraphState) -> ChatGraphState:
    content = state.get("response_content", "")
    if not content:
        return state

    user_id = str(state["user"]["_id"])
    msg = await chat_service.save_message(
        session_id=state["session_id"],
        user_id=user_id,
        role="assistant",
        content=content,
        token_count=state.get("output_tokens", 0),
        metadata=state.get("response_metadata", {}),
    )
    state["assistant_message"] = msg
    return state


# ── 6. update_usage ───────────────────────────────────────────────────────────

async def update_usage(state: ChatGraphState) -> ChatGraphState:
    user_id = str(state["user"]["_id"])
    await usage_service.update_usage(
        user_id=user_id,
        input_tokens=state.get("input_tokens", 0),
        output_tokens=state.get("output_tokens", 0),
    )
    return state
