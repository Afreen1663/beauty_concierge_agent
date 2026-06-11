"""
memory.py — Session state management.

In-memory store for prototype; Supabase used for persistence where possible.
Each session tracks: visitor details, conversation stage, intent history,
pending slot/service, screening progress, and booking references.
"""

from datetime import datetime, timezone
from typing import Optional
from api.database import supabase

_sessions: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT SESSION FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def _default_session(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "stage": "collect_name",
        "client_id": None,
        "user_tier": "visitor",

        # Visitor profile
        "visitor_name": None,
        "visitor_phone": None,
        "visitor_email": None,
        "visitor_contact": None,         # legacy alias (phone or email)

        # Conversation
        "conversation_history": [],
        "last_intent": None,
        "turn": 0,

        # Service / booking context
        "last_service_id": None,
        "last_service_name": None,
        "last_branch_id": None,
        "last_slot_id": None,
        "last_booking_ref": None,
        "last_artist_id": None,

        # Slot selection flow
        "pending_slots": [],
        "pending_service": None,
        "pending_slot": None,

        # Consultation flow (T2)
        "pending_consultation_service_id": None,
        "pending_consultation_branch_id": None,

        # Screening flow (T3)
        "screening_answers": {},
        "screening_service_id": None,
        "screening_service_category": None,

        # Flags
        "needs_name_after": False,
        "needs_contact_after": False,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CORE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = _default_session(session_id)
        _persist_session(session_id)
    return _sessions[session_id]


def update_session(session_id: str, updates: dict) -> None:
    session = get_session(session_id)
    session.update(updates)
    _persist_session(session_id)


def add_turn(session_id: str, user_message: str, assistant_message: str) -> None:
    session = get_session(session_id)
    session["conversation_history"].append({"role": "user", "content": user_message})
    session["conversation_history"].append({"role": "assistant", "content": assistant_message})
    session["turn"] += 1
    _persist_session(session_id)


def get_history(session_id: str, last_n: int = 6) -> list:
    session = get_session(session_id)
    return session["conversation_history"][-(last_n * 2):]


def set_client(session_id: str, client_id: str) -> None:
    update_session(session_id, {
        "client_id": client_id,
        "user_tier": "client",
        "stage": "ready",
    })


def clear_screening(session_id: str) -> None:
    update_session(session_id, {
        "screening_answers": {},
        "screening_service_id": None,
        "screening_service_category": None,
    })


# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE PERSISTENCE (non-fatal)
# ─────────────────────────────────────────────────────────────────────────────

def _persist_session(session_id: str) -> None:
    session = _sessions.get(session_id, {})
    try:
        supabase.table("sessions").upsert({
            "id": session_id,
            "channel": "web",
            "user_tier": session.get("user_tier", "visitor"),
            "client_id": session.get("client_id"),
            "status": session.get("status", "active"),
            "last_intent": session.get("last_intent"),
            "last_booking_ref": session.get("last_booking_ref"),
            "stage": session.get("stage", "collect_name"),
            "visitor_name": session.get("visitor_name"),
            "visitor_contact": session.get("visitor_contact"),
            "turn": session.get("turn", 0),
        }).execute()
    except Exception as e:
        print(f"[MEMORY] Non-fatal session persist error: {e}")
