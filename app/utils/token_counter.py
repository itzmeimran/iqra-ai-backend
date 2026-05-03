"""
Best-effort token counting without calling the LLM.
Uses tiktoken (cl100k_base) as a universal approximation.
Falls back to word-count * 1.3 if tiktoken is unavailable.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        try:
            return len(_enc.encode(text))
        except Exception:
            return _word_fallback(text)

except Exception:
    logger.warning("tiktoken not available, using word-count fallback for token counting.")

    def count_tokens(text: str) -> int:
        return _word_fallback(text)


def _word_fallback(text: str) -> int:
    return max(1, int(len(text.split()) * 1.33))
