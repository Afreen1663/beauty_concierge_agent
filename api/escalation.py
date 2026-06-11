from api.database import supabase
from api.memory import update_session


def escalate_to_human(session_id: str, reason: str = "user_requested") -> dict:
    """
    Marks the session as escalated and logs it.
    In production this would POST to a receptionist webhook.
    """
    try:
        update_session(session_id, {"status": "escalated"})

        supabase.table("sessions").update(
            {"status": "escalated"}
        ).eq("id", session_id).execute()

        # Mock webhook — in production this posts to receptionist console
        print(f"[ESCALATION] Session {session_id} escalated. Reason: {reason}")

    except Exception as e:
        print(f"Escalation logging error: {e}")

    return {
        "status": "ESCALATED",
        "message": (
            "Of course — I'll flag this for one of our team members right away. "
            "Someone will be in touch with you shortly. "
            "In the meantime, you're also welcome to call either branch directly."
        )
    }