from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.jwt import create_access_token, create_refresh_token
from app.db.mongodb import get_db
from app.schemas import (
    RegisterRequest,
    LoginRequest,
    GoogleAuthRequest,
    AuthResponse,
    UserResponse,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_user(doc: dict) -> UserResponse:
    return UserResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        avatarUrl=doc.get("avatarUrl"),
        role=doc.get("role", "user"),
        plan=doc.get("plan", "free"),
        createdAt=doc["createdAt"],
    )


def _make_tokens(user_id: str) -> tuple[str, str]:
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    return access_token, refresh_token


async def register_user(body: RegisterRequest) -> AuthResponse:
    db = get_db()

    email = body.email.lower().strip()

    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    now = _utcnow()

    user_doc = {
        "name": body.name,
        "email": email,
        "passwordHash": hash_password(body.password),
        "authProvider": "local",
        "googleId": None,
        "avatarUrl": None,
        "role": "user",
        "plan": "free",
        "isActive": True,
        "refreshToken": None,
        "createdAt": now,
        "updatedAt": now,
    }

    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    user_id = str(result.inserted_id)
    access_token, refresh_token = _make_tokens(user_id)

    await db.users.update_one(
        {"_id": result.inserted_id},
        {
            "$set": {
                "refreshToken": hash_password(refresh_token),
                "updatedAt": _utcnow(),
            }
        },
    )

    return AuthResponse(
        user=_serialize_user(user_doc),
        accessToken=access_token,
        refreshToken=refresh_token,
    )


async def login_user(body: LoginRequest) -> AuthResponse:
    db = get_db()

    email = body.email.lower().strip()

    user = await db.users.find_one({"email": email})

    if not user or user.get("authProvider") != "local":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(body.password, user["passwordHash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.get("isActive", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    user_id = str(user["_id"])
    access_token, refresh_token = _make_tokens(user_id)

    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "refreshToken": hash_password(refresh_token),
                "updatedAt": _utcnow(),
                "lastLoginAt": _utcnow(),
            }
        },
    )

    return AuthResponse(
        user=_serialize_user(user),
        accessToken=access_token,
        refreshToken=refresh_token,
    )


async def google_sso(body: GoogleAuthRequest) -> AuthResponse:
    db = get_db()

    try:
        id_info = google_id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {exc}",
        )

    google_id = id_info.get("sub")
    email = id_info.get("email", "").lower().strip()
    name = id_info.get("name")
    avatar = id_info.get("picture")
    email_verified = id_info.get("email_verified")

    if not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google user id not found",
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google email not found",
        )

    if email_verified is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified",
        )

    if not name:
        name = email.split("@")[0]

    now = _utcnow()

    user = await db.users.find_one({"googleId": google_id})

    if not user:
        user = await db.users.find_one({"email": email})

    if user:
        await db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "name": name,
                    "email": email,
                    "googleId": google_id,
                    "avatarUrl": avatar,
                    "authProvider": "google",
                    "isActive": True,
                    "updatedAt": now,
                    "lastLoginAt": now,
                }
            },
        )

        user = await db.users.find_one({"_id": user["_id"]})

    else:
        user_doc = {
            "name": name,
            "email": email,
            "passwordHash": None,
            "authProvider": "google",
            "googleId": google_id,
            "avatarUrl": avatar,
            "role": "user",
            "plan": "free",
            "isActive": True,
            "refreshToken": None,
            "createdAt": now,
            "updatedAt": now,
            "lastLoginAt": now,
        }

        result = await db.users.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        user = user_doc

    user_id = str(user["_id"])
    access_token, refresh_token = _make_tokens(user_id)

    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "refreshToken": hash_password(refresh_token),
                "updatedAt": _utcnow(),
            }
        },
    )

    return AuthResponse(
        user=_serialize_user(user),
        accessToken=access_token,
        refreshToken=refresh_token,
    )


async def refresh_tokens(refresh_token: str) -> dict:
    from app.core.jwt import decode_refresh_token

    payload = decode_refresh_token(refresh_token)
    user_id = payload["sub"]

    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)})

    if not user or not user.get("refreshToken"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    if not verify_password(refresh_token, user["refreshToken"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token mismatch",
        )

    new_access_token, new_refresh_token = _make_tokens(user_id)

    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "refreshToken": hash_password(new_refresh_token),
                "updatedAt": _utcnow(),
            }
        },
    )

    return {
        "accessToken": new_access_token,
        "refreshToken": new_refresh_token,
        "tokenType": "bearer",
    }


async def logout_user(user_id: str) -> None:
    db = get_db()

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "refreshToken": None,
                "updatedAt": _utcnow(),
            }
        },
    )