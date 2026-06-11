"""
logger.py — Structured turn-level logging to Supabase.

Logs every agent turn including intent, tool calls, response, latency,
and escalation status. All errors are non-fatal.
"""

from datetime import datetime, timezone
from api.database import supabase


def log_turn(
    session_id: str,
    turn: int,
    user_message: str,
    intent: str,
    confidence: float,
    tool_called: str,
    tool_result: dict,
    agent_response: str,
    latency_ms: int,
    escalated: bool = False,
    entities: dict = None,
    channel: str = "web",
) -> None:
    """
    Logs a single conversation turn to the agent_logs table.
    Silently swallows all errors — logging must never break the chat flow.
    """
    try:
        supabase.table("agent_logs").insert({
            "session_id": session_id,
            "turn": turn,
            "channel": channel,
            "user_message": user_message,
            "intent": intent,
            "confidence": confidence,
            "entities_extracted": entities or {},
            "tool_called": tool_called,
            "tool_result": tool_result,
            "agent_response": agent_response,
            "latency_ms": latency_ms,
            "escalated": escalated,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        print(f"[LOGGER] Non-fatal logging error: {e}")


def log_error(
    session_id: str,
    error_type: str,
    error_detail: str,
    context: dict = None,
) -> None:
    """
    Logs an error event to Supabase for debugging.
    """
    try:
        supabase.table("error_logs").insert({
            "session_id": session_id,
            "error_type": error_type,
            "error_detail": error_detail,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        print(f"[LOGGER] Non-fatal error log failure: {e}")
