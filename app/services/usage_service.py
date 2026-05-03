from __future__ import annotations
from datetime import datetime, timezone, date
from typing import Optional
from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongodb import get_db

# Default plan limits (seed into DB or hardcode here as fallback)
PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "dailyTokenLimit": 10_000,
        "monthlyTokenLimit": 100_000,
        "maxChats": 20,
        "maxMessagesPerChat": 50,
    },
    "pro": {
        "dailyTokenLimit": 100_000,
        "monthlyTokenLimit": 2_000_000,
        "maxChats": 500,
        "maxMessagesPerChat": 1_000,
    },
    "enterprise": {
        "dailyTokenLimit": 1_000_000,
        "monthlyTokenLimit": 50_000_000,
        "maxChats": 99_999,
        "maxMessagesPerChat": 99_999,
    },
}


def _today() -> str:
    return date.today().isoformat()


def _this_month() -> str:
    return date.today().strftime("%Y-%m")


async def get_plan_limits(user: dict) -> dict:
    plan = user.get("plan", "free")
    db = get_db()
    plan_doc = await db.plans.find_one({"name": plan})
    if plan_doc:
        return plan_doc
    return {"name": plan, **PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])}


async def get_today_usage(user_id: str) -> dict:
    db = get_db()
    doc = await db.usage.find_one({"userId": user_id, "date": _today()})
    return doc or {"userId": user_id, "date": _today(), "inputTokens": 0,
                   "outputTokens": 0, "totalTokens": 0, "requestCount": 0}


async def get_monthly_total(user_id: str) -> int:
    db = get_db()
    month_prefix = _this_month()
    pipeline = [
        {"$match": {"userId": user_id, "date": {"$regex": f"^{month_prefix}"}}},
        {"$group": {"_id": None, "total": {"$sum": "$totalTokens"}}},
    ]
    result = await db.usage.aggregate(pipeline).to_list(1)
    return result[0]["total"] if result else 0


async def check_limits(user: dict, estimated_input_tokens: int) -> None:
    """Raise 429 if user has exceeded daily or monthly token limits."""
    limits = await get_plan_limits(user)
    user_id = str(user["_id"])

    daily = await get_today_usage(user_id)
    monthly = await get_monthly_total(user_id)

    daily_used = daily.get("totalTokens", 0)
    daily_limit = limits["dailyTokenLimit"]
    monthly_limit = limits["monthlyTokenLimit"]

    if daily_used + estimated_input_tokens > daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily token limit exceeded ({daily_used}/{daily_limit}). Resets tomorrow.",
        )

    if monthly + estimated_input_tokens > monthly_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly token limit exceeded ({monthly}/{monthly_limit}). Resets next month.",
        )


async def update_usage(user_id: str, input_tokens: int, output_tokens: int) -> None:
    """Upsert today's usage record."""
    db = get_db()
    total = input_tokens + output_tokens
    await db.usage.update_one(
        {"userId": user_id, "date": _today()},
        {
            "$inc": {
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "totalTokens": total,
                "requestCount": 1,
            }
        },
        upsert=True,
    )


async def get_usage_response(user: dict) -> dict:
    user_id = str(user["_id"])
    daily = await get_today_usage(user_id)
    monthly = await get_monthly_total(user_id)
    return {
        "date": daily.get("date", _today()),
        "inputTokens": daily.get("inputTokens", 0),
        "outputTokens": daily.get("outputTokens", 0),
        "totalTokens": daily.get("totalTokens", 0),
        "requestCount": daily.get("requestCount", 0),
        "monthlyTotal": monthly,
    }


async def get_limits_response(user: dict) -> dict:
    user_id = str(user["_id"])
    limits = await get_plan_limits(user)
    daily = await get_today_usage(user_id)
    monthly = await get_monthly_total(user_id)

    daily_used = daily.get("totalTokens", 0)
    monthly_used = monthly
    dl = limits["dailyTokenLimit"]
    ml = limits["monthlyTokenLimit"]

    return {
        "plan": user.get("plan", "free"),
        "dailyTokenLimit": dl,
        "monthlyTokenLimit": ml,
        "maxChats": limits["maxChats"],
        "maxMessagesPerChat": limits["maxMessagesPerChat"],
        "dailyUsed": daily_used,
        "monthlyUsed": monthly_used,
        "dailyRemaining": max(0, dl - daily_used),
        "monthlyRemaining": max(0, ml - monthly_used),
    }
