from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("MongoDB client not initialized. Call connect_db() first.")
    return _client


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not initialized. Call connect_db() first.")
    return _db


async def connect_db() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    _db = _client[settings.mongodb_db_name]
    await _ensure_indexes()
    logger.info("✅ MongoDB connected: %s", settings.mongodb_db_name)


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


async def _ensure_indexes() -> None:
    db = _db
    # users
    await db.users.create_index([("email", ASCENDING)], unique=True)
    await db.users.create_index([("googleId", ASCENDING)], sparse=True)

    # chat_sessions
    await db.chat_sessions.create_index([("userId", ASCENDING)])
    await db.chat_sessions.create_index([("updatedAt", DESCENDING)])

    # messages
    await db.messages.create_index([("sessionId", ASCENDING)])
    await db.messages.create_index([("createdAt", ASCENDING)])

    # usage — unique per user per date
    await db.usage.create_index([("userId", ASCENDING), ("date", ASCENDING)], unique=True)

    logger.info("✅ MongoDB indexes ensured")
