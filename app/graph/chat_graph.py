"""
LangGraph workflow for the chat pipeline.

Flow:
  validate_token_limit
    → load_chat_history
    → save_user_message
    → call_llm
    → save_assistant_message
    → update_usage
    → END
"""
from __future__ import annotations
from langgraph.graph import StateGraph, END
from app.graph.state import ChatGraphState
from app.graph.nodes import (
    validate_token_limit,
    load_chat_history,
    save_user_message,
    call_llm,
    save_assistant_message,
    update_usage,
)


def _should_continue(state: ChatGraphState) -> str:
    """Conditional edge — stop the graph early if an error occurred."""
    return "stop" if state.get("error") else "continue"


def build_chat_graph() -> StateGraph:
    graph = StateGraph(ChatGraphState)

    # Add nodes
    graph.add_node("validate_token_limit", validate_token_limit)
    graph.add_node("load_chat_history", load_chat_history)
    graph.add_node("save_user_message", save_user_message)
    graph.add_node("call_llm", call_llm)
    graph.add_node("save_assistant_message", save_assistant_message)
    graph.add_node("update_usage", update_usage)

    # Entry point
    graph.set_entry_point("validate_token_limit")

    # Conditional edge after limit check
    graph.add_conditional_edges(
        "validate_token_limit",
        _should_continue,
        {"continue": "load_chat_history", "stop": END},
    )

    # Linear edges
    graph.add_edge("load_chat_history",      "save_user_message")
    graph.add_edge("save_user_message",      "call_llm")
    graph.add_edge("call_llm",               "save_assistant_message")
    graph.add_edge("save_assistant_message", "update_usage")
    graph.add_edge("update_usage",           END)

    return graph.compile()


# Singleton compiled graph — import this everywhere
chat_graph = build_chat_graph()
