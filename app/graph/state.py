from __future__ import annotations
from typing import List, Optional, Any
from typing_extensions import TypedDict


class ChatGraphState(TypedDict):
    # Inputs
    user: dict
    session_id: str
    user_content: str
    model: Optional[str]

    # Loaded during graph execution
    session: Optional[dict]
    history: List[dict]           # raw message dicts from DB

    # Token tracking
    input_tokens: int
    output_tokens: int

    # LLM output
    response_content: str
    response_metadata: dict

    # Saved documents
    user_message: Optional[dict]
    assistant_message: Optional[dict]

    # Control
    error: Optional[str]
    stream_chunks: List[str]      # populated during streaming
