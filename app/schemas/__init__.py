from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    idToken: str = Field(..., min_length=1)


class RefreshTokenRequest(BaseModel):
    refreshToken: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    avatarUrl: Optional[str] = None
    role: str
    plan: str
    createdAt: datetime


class AuthResponse(BaseModel):
    user: UserResponse
    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"


# ── Chat Sessions ─────────────────────────────────────────────────────────────

class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Chat"
    model: Optional[str] = None


class UpdateChatRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: str
    userId: str
    title: str
    model: str
    createdAt: datetime
    updatedAt: datetime
    messageCount: int = 0


class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionResponse]
    total: int


# ── Messages ─────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=32_000)
    model: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    sessionId: str
    role: str
    content: str
    tokenCount: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime


class ChatWithMessagesResponse(BaseModel):
    session: ChatSessionResponse
    messages: List[MessageResponse]


# ── Usage ─────────────────────────────────────────────────────────────────────

class UsageResponse(BaseModel):
    date: str
    inputTokens: int
    outputTokens: int
    totalTokens: int
    requestCount: int
    monthlyTotal: int = 0


class PlanLimitsResponse(BaseModel):
    plan: str
    dailyTokenLimit: int
    monthlyTokenLimit: int
    maxChats: int
    maxMessagesPerChat: int
    dailyUsed: int
    monthlyUsed: int
    dailyRemaining: int
    monthlyRemaining: int


# ── Models ────────────────────────────────────────────────────────────────────

class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    isAvailable: bool
    contextLength: Optional[int] = None


class ModelsResponse(BaseModel):
    models: List[ModelInfo]
    defaultModel: str


class SelectModelRequest(BaseModel):
    model: str


# ── Generic ───────────────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    timestamp: datetime