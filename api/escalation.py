"""
escalation.py — Human escalation handler.

Marks the session as escalated, logs the reason, and fires a webhook
(mocked for prototype) to notify the reception team.
"""

import os
from datetime import datetime, timezone
from api.database import supabase
from api.memory import update_session


ESCALATION_WEBHOOK_URL = os.getenv("ESCALATION_WEBHOOK_URL", "")

ESCALATION_REASONS = {
    "user_requested": "The client requested to speak with a team member.",
    "low_confidence": "The agent could not confidently understand the request.",
    "out_of_scope": "The request is outside the agent's capabilities.",
    "screening_flagged": "Medical screening flagged a potential contraindication.",
    "repeated_failure": "The agent failed to resolve the request after multiple attempts.",
}


def escalate_to_human(session_id: str, reason: str = "user_requested") -> dict:
    """
    Escalates a session to a human agent.

    1. Updates in-memory and Supabase session status to 'escalated'
    2. Logs the escalation event
    3. Fires a webhook to the reception console (mocked in prototype)

    Returns a dict with status and the message to send to the user.
    """
    reason_text = ESCALATION_REASONS.get(reason, reason)

    try:
        update_session(session_id, {"status": "escalated"})

        supabase.table("sessions").update(
            {"status": "escalated"}
        ).eq("id", session_id).execute()

        supabase.table("escalations").insert({
            "session_id": session_id,
            "reason": reason,
            "reason_text": reason_text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

    except Exception as e:
        print(f"[ESCALATION] Supabase log error (non-fatal): {e}")

    # Fire webhook if configured (production: POST to receptionist console)
    _fire_webhook(session_id, reason, reason_text)

    return {
        "status": "ESCALATED",
        "message": (
            "Of course — I'll connect you with one of our team members right away. "
            "Someone will be in touch with you shortly. "
            "In the meantime, you're also welcome to call either branch directly."
        ),
    }


def _fire_webhook(session_id: str, reason: str, reason_text: str) -> None:
    """
    Fires a webhook to the reception console.
    In the prototype this is a mock — in production, POST to a real endpoint.
    """
    if ESCALATION_WEBHOOK_URL and ESCALATION_WEBHOOK_URL.startswith("http"):
        try:
            import requests
            requests.post(ESCALATION_WEBHOOK_URL, json={
                "session_id": session_id,
                "reason": reason,
                "reason_text": reason_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, timeout=3)
        except Exception as e:
            print(f"[ESCALATION] Webhook error (non-fatal): {e}")
    else:
        print(f"[ESCALATION] Session {session_id[:8]}... escalated. Reason: {reason_text}")
