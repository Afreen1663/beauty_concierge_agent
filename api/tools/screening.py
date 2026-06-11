"""
screening.py — Medical screening workflow for T3 services.

Manages the 6-question health screening, parses yes/no answers,
submits completed screenings to Supabase, and returns the result
with an appropriate reference and status.
"""

import json
import os
import random
import string
from datetime import datetime, timezone
from api.database import supabase


def _save_screening_fallback(record: dict) -> None:
    """
    Writes a screening record to a local JSON file when Supabase is unavailable.
    File: screenings_fallback.jsonl (one JSON object per line, easy to import later).
    """
    try:
        path = os.path.join(os.path.dirname(__file__), "..", "screenings_fallback.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as fe:
        print(f"[SCREENING] Fallback file write also failed: {fe}")


SCREENING_QUESTIONS = [
    {
        "id": "q1_pregnant",
        "question": "Are you pregnant or breastfeeding?",
        "flag_if": True,
    },
    {
        "id": "q2_blood_thinners",
        "question": "Are you currently taking blood thinners or anticoagulants?",
        "flag_if": True,
    },
    {
        "id": "q3_allergies",
        "question": "Do you have any known allergies to anaesthetics, lidocaine, or hyaluronic acid?",
        "flag_if": True,
    },
    {
        "id": "q4_prior_procedures",
        "question": "Have you had any facial surgery or aesthetic procedures in the last 6 months?",
        "flag_if": True,
    },
    {
        "id": "q5_active_infection",
        "question": "Do you have any active skin infections, cold sores, or open wounds on the treatment area?",
        "flag_if": True,
    },
    {
        "id": "q6_autoimmune",
        "question": "Do you have any autoimmune conditions or are you on immunosuppressant medication?",
        "flag_if": True,
    },
]

_YES_PATTERNS = [
    "yes", "yeah", "yep", "yup", "i am", "i do", "i have",
    "correct", "absolutely", "definitely", "sure", "of course",
    "i'm pregnant", "i'm breastfeeding", "i take", "i use",
]
_NO_PATTERNS = [
    "no", "nope", "nah", "don't", "dont", "haven't", "havent",
    "not really", "i do not", "i don't", "none", "neither",
    "no i'm not", "i'm not",
]

# Words that signal the user is asking a question rather than answering yes/no
_CLARIFICATION_SIGNALS = [
    "what", "what's", "whats", "what is", "what are",
    "mean", "means", "meaning",
    "explain", "elaborate", "clarify", "tell me",
    "don't understand", "dont understand", "not sure what",
    "what do you mean", "could you explain",
    "?",
]

# Phrases that indicate the booking/screening is for someone else
_FOR_SOMEONE_ELSE_SIGNALS = [
    "for my daughter", "for my son", "for my friend", "for my sister",
    "for my brother", "for my mother", "for my mom", "for my mum",
    "for my father", "for my dad", "for my wife", "for my husband",
    "for my partner", "for someone else", "not for me", "it's not me",
    "she's", "he's", "they're", "her", "him", "them",
]


def is_clarification_question(text: str) -> bool:
    """
    Returns True if the user's message looks like a clarification question
    rather than a yes/no answer to a screening question.
    """
    lower = text.lower().strip()
    return any(signal in lower for signal in _CLARIFICATION_SIGNALS)


def is_for_someone_else(text: str) -> bool:
    """
    Returns True if the user indicates the treatment/screening is for
    someone other than themselves.
    """
    lower = text.lower().strip()
    return any(signal in lower for signal in _FOR_SOMEONE_ELSE_SIGNALS)


def get_next_question(answers_so_far: dict) -> dict | None:
    """Returns the next unanswered screening question, or None if all complete."""
    for q in SCREENING_QUESTIONS:
        if q["id"] not in answers_so_far:
            return q
    return None


def get_question_number(question_id: str) -> int:
    """Returns the 1-based index of a question in the screening list."""
    for i, q in enumerate(SCREENING_QUESTIONS):
        if q["id"] == question_id:
            return i + 1
    return 1


def parse_yes_no(text: str) -> bool | None:
    """
    Parses a user response to a yes/no question.
    Returns True (yes), False (no), or None (unclear).
    """
    cleaned = text.lower().strip()

    for pattern in _NO_PATTERNS:
        if pattern in cleaned:
            return False

    for pattern in _YES_PATTERNS:
        if pattern in cleaned:
            return True

    return None


def submit_screening(
    service_id: str,
    service_category: str,
    answers: dict,
    client_id: str = None,
    visitor_name: str = None,
    visitor_contact: str = None,
) -> dict:
    """
    Submits a completed health screening.

    The Supabase save is NON-FATAL — the user always receives the correct
    confirmation message regardless of database availability. Failed saves
    are written to a local JSON fallback file for manual review.
    """
    flagged = [
        q["id"]
        for q in SCREENING_QUESTIONS
        if answers.get(q["id"]) is True and q["flag_if"] is True
    ]

    year = datetime.now().year
    suffix = "".join(random.choices(string.digits, k=4))
    screening_ref = f"SCR-{year}-{suffix}"

    record = {
        "id": screening_ref,
        "service_category": service_category,
        "answers": answers,
        "flagged_questions": flagged,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if client_id:
        record["client_id"] = client_id
    else:
        record["visitor_name"] = visitor_name or ""
        record["visitor_contact"] = visitor_contact or ""

    # ── Supabase save (non-fatal) ─────────────────────────────────────────
    try:
        supabase.table("medical_screenings").insert(record).execute()
    except Exception as e:
        print(f"[SCREENING] Supabase save failed ({type(e).__name__}: {e}) — writing to fallback file")
        _save_screening_fallback(record)
    # ─────────────────────────────────────────────────────────────────────
    # Always return a proper response — never block the user on a DB error
    # ─────────────────────────────────────────────────────────────────────

    if flagged:
        return {
            "status": "FLAGGED",
            "screening_ref": screening_ref,
            "flagged_questions": flagged,
            "message": (
                "Thank you for completing the screening. Based on your answers, "
                "our medical team needs to review your case before we can proceed. "
                f"Someone will be in touch within 24 hours. Reference: {screening_ref}."
            ),
        }

    return {
        "status": "SUBMITTED",
        "screening_ref": screening_ref,
        "flagged_questions": [],
        "message": (
            "Your screening has been submitted. Our medical team will review it "
            f"and get back to you within 24 hours. Reference: {screening_ref}."
        ),
    }