from datetime import datetime, timezone

# In-memory session store — keyed by session_id
_sessions = {}


def get_session(session_id: str) -> dict:
    """Returns existing session or creates a new one."""
    if session_id not in _sessions:
        _sessions[session_id] = {
            "session_id": session_id,
            "client_id": None,
            "user_tier": "visitor",
            "conversation_history": [],
            "last_intent": None,
            "last_service_id": None,
            "last_service_name": None,
            "last_slot_id": None,
            "last_branch_id": None,
            "last_booking_ref": None,
            "screening_answers": {},
            "screening_service_id": None,
            "screening_service_category": None,
            "visitor_name": None,
            "visitor_contact": None,
            "status": "active",
            "turn": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    return _sessions[session_id]


def update_session(session_id: str, updates: dict):
    """Merges updates into an existing session."""
    session = get_session(session_id)
    session.update(updates)


def add_turn(session_id: str, user_message: str, assistant_message: str):
    """Appends a conversation turn to the session history."""
    session = get_session(session_id)
    session["conversation_history"].append({
        "role": "user",
        "content": user_message
    })
    session["conversation_history"].append({
        "role": "assistant",
        "content": assistant_message
    })
    session["turn"] += 1


def get_history(session_id: str, last_n: int = 6) -> list:
    """Returns the last N turns of conversation history."""
    session = get_session(session_id)
    return session["conversation_history"][-last_n:]


def set_client(session_id: str, client_id: str):
    """Upgrades session to authenticated client tier."""
    update_session(session_id, {
        "client_id": client_id,
        "user_tier": "client"
    })


def clear_screening(session_id: str):
    """Resets screening state after submission."""
    update_session(session_id, {
        "screening_answers": {},
        "screening_service_id": None,
        "screening_service_category": None,
    })