from __future__ import annotations
import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.schemas import (
    CreateChatRequest, UpdateChatRequest, SendMessageRequest,
    ChatSessionResponse, ChatSessionListResponse, ChatWithMessagesResponse,
    MessageResponse,
)
from app.services import chat_service, llm_service, usage_service
from app.services.chat_service import auto_title_session, save_message
from app.graph.chat_graph import chat_graph
from app.middlewares.auth_middleware import get_current_user
from app.utils.token_counter import count_tokens
from app.core.config import settings

router = APIRouter(prefix="/api/chats", tags=["Chat"])
logger = logging.getLogger(__name__)


# ── Helper ────────────────────────────────────────────────────────────────────

def _session_resp(doc: dict) -> ChatSessionResponse:
    return ChatSessionResponse(**{
        "id": str(doc["_id"]),
        "userId": doc["userId"],
        "title": doc["title"],
        "model": doc["model"],
        "createdAt": doc["createdAt"],
        "updatedAt": doc["updatedAt"],
        "messageCount": doc.get("messageCount", 0),
    })


def _msg_resp(doc: dict) -> MessageResponse:
    return MessageResponse(**{
        "id": str(doc["_id"]),
        "sessionId": doc["sessionId"],
        "role": doc["role"],
        "content": doc["content"],
        "tokenCount": doc.get("tokenCount", 0),
        "metadata": doc.get("metadata", {}),
        "createdAt": doc["createdAt"],
    })


# ── Session endpoints ─────────────────────────────────────────────────────────

@router.post("", response_model=ChatSessionResponse, status_code=201)
async def create_chat(body: CreateChatRequest, user: dict = Depends(get_current_user)):
    session = await chat_service.create_session(user, body)
    return _session_resp(session)


@router.get("", response_model=ChatSessionListResponse)
async def list_chats(user: dict = Depends(get_current_user)):
    sessions = await chat_service.list_sessions(user)
    return ChatSessionListResponse(sessions=[_session_resp(s) for s in sessions], total=len(sessions))


@router.get("/{chat_id}", response_model=ChatWithMessagesResponse)
async def get_chat(chat_id: str, user: dict = Depends(get_current_user)):
    session = await chat_service.get_session(user, chat_id)
    messages = await chat_service.get_messages(user, chat_id)
    return ChatWithMessagesResponse(
        session=_session_resp(session),
        messages=[_msg_resp(m) for m in messages],
    )


@router.patch("/{chat_id}", response_model=ChatSessionResponse)
async def update_chat(chat_id: str, body: UpdateChatRequest, user: dict = Depends(get_current_user)):
    session = await chat_service.update_session(user, chat_id, body)
    return _session_resp(session)


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, user: dict = Depends(get_current_user)):
    await chat_service.delete_session(user, chat_id)


# ── Message endpoints ─────────────────────────────────────────────────────────

@router.post("/{chat_id}/messages", response_model=MessageResponse)
async def send_message(
    chat_id: str,
    body: SendMessageRequest,
    user: dict = Depends(get_current_user),
):
    """Send a message and get a complete (non-streaming) LLM response."""
    session = await chat_service.get_session(user, chat_id)

    initial_state = {
        "user": user,
        "session_id": chat_id,
        "user_content": body.content,
        "model": body.model or session.get("model") or settings.default_model,
        "session": session,
        "history": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "response_content": "",
        "response_metadata": {},
        "user_message": None,
        "assistant_message": None,
        "error": None,
        "stream_chunks": [],
    }

    final_state = await chat_graph.ainvoke(initial_state)

    if final_state.get("error"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
            if "limit" in (final_state["error"] or "").lower()
            else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=final_state["error"],
        )

    ai_msg = final_state.get("assistant_message")
    if not ai_msg:
        raise HTTPException(status_code=500, detail="No response generated")

    return _msg_resp(ai_msg)


@router.post("/{chat_id}/messages/stream")
async def stream_message(
    chat_id: str,
    body: SendMessageRequest,
    user: dict = Depends(get_current_user),
):
    """Send a message and stream the LLM response via SSE."""
    session = await chat_service.get_session(user, chat_id)
    model = body.model or session.get("model") or settings.default_model
    user_id = str(user["_id"])

    # Pre-flight checks
    estimated = count_tokens(body.content)
    await usage_service.check_limits(user, estimated)

    # Save user message immediately
    user_msg = await save_message(
        session_id=chat_id,
        user_id=user_id,
        role="user",
        content=body.content,
        token_count=estimated,
    )
    await auto_title_session(chat_id, user_id, body.content)

    # Build history — include ALL messages (user message already saved above)
    history = await chat_service.get_messages(user, chat_id)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    async def event_generator() -> AsyncGenerator[str, None]:
        full_response = ""
        try:
            async for chunk in llm_service.stream_chat(messages, model=model):
                full_response += chunk
                yield json.dumps({"type": "chunk", "content": chunk})
                await asyncio.sleep(0)   # yield to event loop

            # Save assistant message
            output_tokens = count_tokens(full_response)
            ai_msg = await save_message(
                session_id=chat_id,
                user_id=user_id,
                role="assistant",
                content=full_response,
                token_count=output_tokens,
            )
            await usage_service.update_usage(user_id, estimated, output_tokens)

            yield json.dumps({
                "type": "done",
                "messageId": str(ai_msg["_id"]),
                "inputTokens": estimated,
                "outputTokens": output_tokens,
            })

        except Exception as exc:
            logger.error("Streaming error: %s", exc)
            yield json.dumps({"type": "error", "message": str(exc)})

    return EventSourceResponse(event_generator())


@router.post("/{chat_id}/regenerate", response_model=MessageResponse)
async def regenerate_response(
    chat_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete the last assistant message and regenerate."""
    from app.db.mongodb import get_db
    from bson import ObjectId

    db = get_db()
    session = await chat_service.get_session(user, chat_id)
    user_id = str(user["_id"])

    # Get and delete last assistant message
    last_ai = await chat_service.get_last_assistant_message(chat_id)
    if last_ai:
        await db.messages.delete_one({"_id": ObjectId(last_ai["_id"])})

    # Get the last user message for context
    history = await chat_service.get_messages(user, chat_id)
    if not history:
        raise HTTPException(status_code=400, detail="No messages to regenerate from")

    model = session.get("model") or settings.default_model
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    estimated = sum(count_tokens(m["content"]) for m in history)
    await usage_service.check_limits(user, 0)

    response_text = await llm_service.complete_chat(messages, model=model)
    output_tokens = count_tokens(response_text)

    ai_msg = await save_message(
        session_id=chat_id,
        user_id=user_id,
        role="assistant",
        content=response_text,
        token_count=output_tokens,
        metadata={"regenerated": True},
    )
    await usage_service.update_usage(user_id, 0, output_tokens)

    return _msg_resp(ai_msg)