"""
GenAI Chat Backend — FastAPI entry point
"""
from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.mongodb import connect_db, close_db
from app.api import auth, chat, usage, models

# ── LangSmith tracing ─────────────────────────────────────────────────────────
if settings.langchain_tracing_v2.lower() == "true":
    os.environ["LANGCHAIN_TRACING_V2"]  = "true"
    os.environ["LANGCHAIN_ENDPOINT"]    = settings.langchain_endpoint
    os.environ["LANGCHAIN_PROJECT"]     = settings.langchain_project
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key



# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.app_env == "development" else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)




# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # logger.info("🚀 Starting GenAI Chat Backend (%s)", settings.app_env)
    await connect_db()
    await _seed_plans()
    yield
    await close_db()
    logger.info("💤 Shutdown complete")


async def _seed_plans() -> None:
    """Ensure plan documents exist in MongoDB."""
    from app.db.mongodb import get_db
    from app.services.usage_service import PLAN_LIMITS

    db = get_db()
    for name, limits in PLAN_LIMITS.items():
        await db.plans.update_one(
            {"name": name},
            {"$setOnInsert": {"name": name, **limits}},
            upsert=True,
        )
    logger.info("✅ Plans seeded")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GenAI Chat API",
    version="1.0.0",
    description="LangGraph-powered chat backend with local LLM support",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Exception Handler ───────────────────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": str(exc),
        },
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error"},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(usage.router)
app.include_router(models.router)


# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/api/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/llm/health", tags=["Health"])
async def llm_health():
    from app.services.llm_service import check_llm_health
    return await check_llm_health()
