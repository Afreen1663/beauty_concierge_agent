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
) -> None:
    """
    Logs a single conversation turn to Supabase agent_logs.
    Non-blocking — errors are printed but never raised.
    """
    try:
        supabase.table("agent_logs").insert({
            "session_id": session_id,
            "turn": turn,
            "channel": "web",
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