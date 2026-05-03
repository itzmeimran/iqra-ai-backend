from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongodb import get_db
from app.core.config import settings
from app.schemas import CreateChatRequest, UpdateChatRequest


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _str_id(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(user: dict, body: CreateChatRequest) -> dict:
    db = get_db()
    user_id = str(user["_id"])

    # Respect maxChats limit
    from app.services.usage_service import get_plan_limits
    limits = await get_plan_limits(user)
    count = await db.chat_sessions.count_documents({"userId": user_id})
    if count >= limits["maxChats"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Chat limit reached ({limits['maxChats']} for {user.get('plan','free')} plan)",
        )

    now = _utcnow()
    doc = {
        "userId": user_id,
        "title": body.title or "New Chat",
        "model": body.model or settings.default_model,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db.chat_sessions.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc["messageCount"] = 0
    return doc


async def list_sessions(user: dict) -> List[dict]:
    db = get_db()
    user_id = str(user["_id"])
    cursor = db.chat_sessions.find({"userId": user_id}).sort("updatedAt", -1)
    sessions = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        count = await db.messages.count_documents({"sessionId": doc["_id"]})
        doc["messageCount"] = count
        sessions.append(doc)
    return sessions


async def get_session(user: dict, session_id: str) -> dict:
    db = get_db()
    try:
        obj_id = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID")

    doc = await db.chat_sessions.find_one({"_id": obj_id, "userId": str(user["_id"])})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    doc["_id"] = str(doc["_id"])
    count = await db.messages.count_documents({"sessionId": session_id})
    doc["messageCount"] = count
    return doc


async def update_session(user: dict, session_id: str, body: UpdateChatRequest) -> dict:
    db = get_db()
    try:
        obj_id = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    updates: dict = {"updatedAt": _utcnow()}
    if body.title is not None:
        updates["title"] = body.title
    if body.model is not None:
        updates["model"] = body.model

    result = await db.chat_sessions.update_one(
        {"_id": obj_id, "userId": str(user["_id"])},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chat session not found")

    return await get_session(user, session_id)


async def delete_session(user: dict, session_id: str) -> None:
    db = get_db()
    try:
        obj_id = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    result = await db.chat_sessions.delete_one({"_id": obj_id, "userId": str(user["_id"])})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Cascade delete messages
    await db.messages.delete_many({"sessionId": session_id})


# ── Messages ──────────────────────────────────────────────────────────────────

async def get_messages(user: dict, session_id: str) -> List[dict]:
    # Verify ownership
    await get_session(user, session_id)
    db = get_db()
    cursor = db.messages.find({"sessionId": session_id}).sort("createdAt", 1)
    msgs = []
    async for m in cursor:
        m["_id"] = str(m["_id"])
        msgs.append(m)
    return msgs


async def save_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    token_count: int = 0,
    metadata: dict | None = None,
) -> dict:
    db = get_db()
    doc = {
        "sessionId": session_id,
        "userId": user_id,
        "role": role,
        "content": content,
        "tokenCount": token_count,
        "metadata": metadata or {},
        "createdAt": _utcnow(),
    }
    result = await db.messages.insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    # Touch session updatedAt
    try:
        await db.chat_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"updatedAt": _utcnow()}},
        )
    except Exception:
        pass

    return doc


async def get_last_assistant_message(session_id: str) -> Optional[dict]:
    db = get_db()
    doc = await db.messages.find_one(
        {"sessionId": session_id, "role": "assistant"},
        sort=[("createdAt", -1)],
    )
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def auto_title_session(session_id: str, user_id: str, user_content: str) -> None:
    """Set the chat title from the first user message (first 50 chars)."""
    db = get_db()
    count = await db.messages.count_documents({"sessionId": session_id})
    if count <= 1:   # just inserted the first message
        title = user_content[:50].strip()
        if len(user_content) > 50:
            title += "…"
        await db.chat_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"title": title, "updatedAt": _utcnow()}},
        )
