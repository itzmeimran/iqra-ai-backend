"""
Run with:
    uvicorn main:app --reload --port 8000

Or via Makefile/Docker.
"""
from app.main import app  # noqa: F401
