"""
Pydantic models representing MongoDB documents.
All models use string IDs to avoid ObjectId serialisation issues.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Literal, Any, Dict
from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── User ─────────────────────────────────────────────────────────────────────

class UserModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    email: str
    passwordHash: Optional[str] = None
    authProvider: Literal["local", "google"] = "local"
    googleId: Optional[str] = None
    avatarUrl: Optional[str] = None
    role: Literal["user", "admin"] = "user"
    plan: Literal["free", "pro", "enterprise"] = "free"
    isActive: bool = True
    refreshToken: Optional[str] = None   # hashed refresh token stored for invalidation
    createdAt: datetime = Field(default_factory=utcnow)
    updatedAt: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


# ── Chat Session ─────────────────────────────────────────────────────────────

class ChatSessionModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    userId: str
    title: str = "New Chat"
    model: str
    createdAt: datetime = Field(default_factory=utcnow)
    updatedAt: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


# ── Message ──────────────────────────────────────────────────────────────────

class MessageModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    sessionId: str
    userId: str
    role: Literal["user", "assistant", "system"]
    content: str
    tokenCount: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


# ── Usage ────────────────────────────────────────────────────────────────────

class UsageModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    userId: str
    date: str                   # YYYY-MM-DD
    inputTokens: int = 0
    outputTokens: int = 0
    totalTokens: int = 0
    requestCount: int = 0

    model_config = {"populate_by_name": True}


# ── Plan ─────────────────────────────────────────────────────────────────────

class PlanModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: Literal["free", "pro", "enterprise"]
    dailyTokenLimit: int
    monthlyTokenLimit: int
    maxChats: int
    maxMessagesPerChat: int

    model_config = {"populate_by_name": True}
