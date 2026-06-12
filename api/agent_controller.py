"""
agent_controller.py — Core orchestration layer for Luma booking concierge.

Conversation stage machine:
  collect_name                   — awaiting visitor full name
  collect_phone                  — awaiting visitor phone number
  collect_email                  — awaiting visitor email address
  ready                          — normal intent routing
  awaiting_consultation_confirm  — T2: yes/no to consultation offer
  awaiting_consultation_slots    — T2: picking a consultation slot number
  awaiting_slot_selection        — picking a regular service slot number
  awaiting_confirmation          — confirming a selected slot before booking
  collect_name_for_booking       — mid-flow name collection (regular booking)
  collect_contact_for_booking    — mid-flow contact collection (regular booking)
  collect_name_for_consultation  — mid-flow name collection (consultation booking)
  collect_contact_for_consultation — mid-flow contact collection (consultation)
  screening                      — T3 screening in progress (intercepted pre-intent)
  collect_contact_post_screening — gathering contact after screening submission
"""

import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

from api.intent_classifier import classify_intent
from api.memory import (
    get_session, update_session, add_turn, get_history, clear_screening,
)
from api.tools.availability import (
    check_availability, resolve_service_id, resolve_branch_id, resolve_artist_id,
)
from api.tools.gate_check import check_service_gate
from api.tools.bookings import create_booking
from api.tools.faq import lookup_faq
from api.tools.consultation import get_consultation_service_id
from api.tools.screening import (
    get_next_question, get_question_number, parse_yes_no,
    submit_screening, SCREENING_QUESTIONS,
    is_clarification_question, is_for_someone_else,
)
from api.database import supabase

load_dotenv()
_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_RESPONSE_SYSTEM = """You are Luma, a warm and professional booking assistant 
for a luxury beauty and wellness brand in Dubai. Be natural, conversational, and never robotic. 
Acknowledge what the user said. Use their name occasionally. Maximum 4 sentences unless 
showing a booking summary. Plain text only. Never invent prices or availability."""


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _valid_phone(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return len(digits) >= 7


def _valid_email(text: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", text.strip()))


def _looks_like_name(text: str) -> bool:
    t = text.strip()
    if len(t) < 2 or len(t) > 50:
        return False
    if any(c.isdigit() for c in t):
        return False
    skip_words = [
        "book", "availability", "appoint", "slot", "service", "brow",
        "lash", "inject", "treatment", "lamination", "threading", "spmu",
        "tint", "anti", "wrinkle", "filler", "hello", "hi", "hey",
        "yes", "no", "okay", "ok", "sure", "please",
    ]
    lower = t.lower()
    if any(kw in lower for kw in skip_words):
        return False
    alpha_ratio = sum(c.isalpha() or c == " " for c in t) / len(t)
    return alpha_ratio > 0.85


def _is_yes(text: str) -> bool:
    t = text.lower().strip()
    return any(w in t for w in [
        "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please",
        "go ahead", "book it", "confirm", "correct", "absolutely",
        "definitely", "do it", "sounds good", "great", "let's go",
        "lets go", "perfect", "alright", "all right", "of course",
    ])


def _is_no(text: str) -> bool:
    t = text.lower().strip()
    return any(w in t for w in [
        "no", "nope", "nah", "cancel", "stop", "don't",
        "dont", "never mind", "nevermind", "not now", "skip",
    ])


def _parse_slot_choice(text: str, slot_count: int) -> int | None:
    t = text.strip()
    if t.isdigit():
        idx = int(t) - 1
        if 0 <= idx < slot_count:
            return idx
        return None
    m = re.search(r"\b([1-9])\b", t)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < slot_count:
            return idx
        return None
    return -1


def _format_slots(slots: list) -> str:
    DUBAI_TZ = timezone(timedelta(hours=4))
    lines = []
    for i, s in enumerate(slots, 1):
        try:
            dt = datetime.fromisoformat(s["start_time"].replace("Z", "+00:00"))
            dt_dubai = dt.astimezone(DUBAI_TZ)
            formatted = dt_dubai.strftime("%A, %d %B at %I:%M %p")
        except Exception:
            formatted = s.get("start_time", "")[:16]
        branch = (
            s.get("branches", {}).get("name", "our branch")
            if isinstance(s.get("branches"), dict)
            else "our branch"
        )
        lines.append(f"{i}. {formatted} — {branch}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _generate_response(tool_result: str, user_message: str, history: list) -> str:
    messages = [{"role": "system", "content": _RESPONSE_SYSTEM}]
    messages.extend(history[-6:])
    messages.append({
        "role": "user",
        "content": (
            f"User said: {user_message}\n\n"
            f"Context / tool result: {tool_result}\n\n"
            "Respond naturally. If it's a booking confirmation, output it exactly as given."
        ),
    })
    try:
        resp = _openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.4,
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return tool_result


def _save_visitor(name: str, contact: str) -> None:
    try:
        supabase.table("visitors").upsert(
            {
                "name": name,
                "contact": contact,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="contact",
        ).execute()
    except Exception as e:
        print(f"[VISITOR SAVE] Non-fatal: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# BOOKING / AVAILABILITY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_date_str(raw_date: str | None) -> str | None:
    if not raw_date:
        return None
    today = datetime.now(timezone(timedelta(hours=4)))
    raw = raw_date.lower().strip()
    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    for day_name, weekday in day_map.items():
        if day_name in raw:
            days_ahead = weekday - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            target = today + timedelta(days=days_ahead)
            return target.strftime("%Y-%m-%d")
    if "tomorrow" in raw:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "today" in raw:
        return today.strftime("%Y-%m-%d")
    return raw_date


def _run_availability_and_show_slots(
    session_id: str,
    service_id: str,
    service_name: str,
    entities: dict,
    user_message: str,
    history: list,
    next_stage: str = "awaiting_slot_selection",
) -> str:
    session = get_session(session_id)
    branch_id = session.get("last_branch_id")
    if entities.get("branch") and not branch_id:
        branch_id = resolve_branch_id(entities["branch"])

    artist_id = None
    if entities.get("artist"):
        artist_id = resolve_artist_id(entities["artist"])

    avail = check_availability(
        service_id=service_id,
        branch_id=branch_id,
        date_str=_resolve_date_str(entities.get("date")),
        artist_id=artist_id,
    )

    if avail["status"] == "AVAILABLE":
        slot_text = _format_slots(avail["slots"])
        update_session(session_id, {
            "pending_slots": avail["slots"],
            "last_service_id": service_id,
            "last_service_name": service_name,
            "last_branch_id": branch_id,
            "stage": next_stage,
        })
        date_label = f" on {entities['date']}" if entities.get("date") else ""
        context = (
            f"Available slots for {service_name}{date_label}:\n\n{slot_text}\n\n"
            "Ask the user which slot works for them. Tell them to reply with the number."
        )
        response = _generate_response(context, user_message, history)
    elif avail["alternatives"]:
        slot_text = _format_slots(avail["alternatives"])
        update_session(session_id, {
            "pending_slots": avail["alternatives"],
            "last_service_id": service_id,
            "last_service_name": service_name,
            "last_branch_id": branch_id,
            "stage": next_stage,
        })
        context = (
            f"No slots available for the requested date for {service_name}, "
            f"but here are the next available times:\n\n{slot_text}\n\n"
            "Ask the user if any of these work and tell them to reply with the number."
        )
        response = _generate_response(context, user_message, history)
    else:
        update_session(session_id, {"stage": "ready"})
        response = _generate_response(
            f"No availability found for {service_name}. No alternative slots either.",
            user_message, history,
        )

    return response


# ─────────────────────────────────────────────────────────────────────────────
# T2 CONSULTATION SLOT BOOKING HELPER — shared by two code paths
# ─────────────────────────────────────────────────────────────────────────────

def _book_consultation_slots(
    session_id: str,
    spmu_service_id: str,
    branch_id: str | None,
    service_name: str,
    user_message: str,
    history: list,
) -> str:
    """
    Fetches consultation slots for a T2 service and presents them.
    Used by both the awaiting_consultation_confirm handler and the
    book_consultation intent handler so the logic is never duplicated.
    """
    consult_service_id = get_consultation_service_id(spmu_service_id) or spmu_service_id
    avail = check_availability(consult_service_id, branch_id)

    slots = avail.get("slots") or avail.get("alternatives") or []
    if slots:
        slot_text = _format_slots(slots)
        update_session(session_id, {
            "pending_slots": slots,
            "pending_consultation_service_id": consult_service_id,
            "stage": "awaiting_consultation_slots",
        })
        context = (
            f"Here are the available consultation slots for {service_name}:\n\n"
            f"{slot_text}\n\n"
            "Which works best for you? Just reply with the number."
        )
    else:
        update_session(session_id, {"stage": "ready"})
        context = (
            "No consultation slots are available right now. "
            "Ask the user to call either branch directly and the team will sort them out."
        )

    return _generate_response(context, user_message, history)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN HANDLER
# ─────────────────────────────────────────────────────────────────────────────

def handle_message(session_id: str, user_message: str) -> str:
    session = get_session(session_id)
    history = get_history(session_id)
    stage = session.get("stage", "collect_name")
    name = session.get("visitor_name") or ""

    # ── Clients skip all collection stages ───────────────────────────────────
    if session.get("client_id") and stage in (
        "collect_name", "collect_phone", "collect_email"
    ):
        update_session(session_id, {"stage": "ready"})
        stage = "ready"

    # ─────────────────────────────────────────────────────────────────────────
    # T3 SCREENING INTERCEPTOR — fires before any intent routing
    # ─────────────────────────────────────────────────────────────────────────
    if (
        session.get("screening_service_id")
        and len(session.get("screening_answers", {})) < len(SCREENING_QUESTIONS)
    ):
        answers = session["screening_answers"]

        current_q = None
        for q in SCREENING_QUESTIONS:
            if q["id"] not in answers:
                current_q = q
                break

        if current_q:
            q_num = get_question_number(current_q["id"])

            # User says treatment is for someone else
            if is_for_someone_else(user_message):
                update_session(session_id, {"screening_for": user_message.strip()})
                context = (
                    f"The user clarified that the treatment is for someone else "
                    f"(they said: '{user_message}'). Acknowledge this warmly — say that's "
                    f"fine and the screening questions still apply to that person. "
                    f"Then re-ask this screening question naturally: "
                    f"Question {q_num} of {len(SCREENING_QUESTIONS)}: {current_q['question']}"
                )
                response = _generate_response(context, user_message, history)
                add_turn(session_id, user_message, response)
                return response

            # User is asking for clarification, not answering yes/no
            if is_clarification_question(user_message):
                context = (
                    f"The user is asking for clarification during a medical screening. "
                    f"They said: '{user_message}'. "
                    f"The current screening question is: '{current_q['question']}'. "
                    f"Explain any medical or clinical terms used in that question in simple, "
                    f"friendly language. After explaining, naturally re-ask the same question: "
                    f"Question {q_num} of {len(SCREENING_QUESTIONS)}: {current_q['question']}"
                )
                response = _generate_response(context, user_message, history)
                add_turn(session_id, user_message, response)
                return response

            # Standard yes/no answer
            parsed = parse_yes_no(user_message)
            if parsed is None:
                context = (
                    f"The user's response '{user_message}' is unclear — it's not a clear "
                    f"yes or no. Gently ask them again: "
                    f"Question {q_num} of {len(SCREENING_QUESTIONS)}: {current_q['question']}"
                )
                response = _generate_response(context, user_message, history)
                add_turn(session_id, user_message, response)
                return response

            answers[current_q["id"]] = parsed
            update_session(session_id, {"screening_answers": answers})

            next_q = get_next_question(answers)
            if next_q:
                next_q_num = get_question_number(next_q["id"])
                response = (
                    f"Question {next_q_num} of {len(SCREENING_QUESTIONS)}: "
                    f"{next_q['question']}"
                )
                add_turn(session_id, user_message, response)
                return response

            # All answered — submit
            result = submit_screening(
                service_id=session["screening_service_id"],
                service_category=session["screening_service_category"],
                answers=answers,
                client_id=session.get("client_id"),
                visitor_name=session.get("visitor_name"),
                visitor_contact=session.get("visitor_contact"),
            )
            clear_screening(session_id)
            update_session(session_id, {"stage": "ready"})
            response = result["message"]
            if not session.get("visitor_contact") and not session.get("client_id"):
                response += (
                    "\n\nCould I also take your phone number or email? "
                    "We'll send you updates on your screening review."
                )
                update_session(session_id, {"stage": "collect_contact_post_screening"})
            add_turn(session_id, user_message, response)
            return response

    # ─────────────────────────────────────────────────────────────────────────
    # POST-SCREENING CONTACT COLLECTION
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "collect_contact_post_screening":
        txt = user_message.strip()
        if _valid_phone(txt) or _valid_email(txt):
            update_session(session_id, {
                "visitor_contact": txt,
                "stage": "ready",
            })
            _save_visitor(session.get("visitor_name", ""), txt)
            response = "Noted — we'll be in touch within 24 hours with your screening result."
        else:
            update_session(session_id, {"stage": "ready"})
            response = "No worries — our team will reach out via the contact you provided earlier."
        add_turn(session_id, user_message, response)
        return response

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE: COLLECT NAME
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "collect_name":
        inline = re.search(
            r"(?:i'?m|my name is|i am|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            user_message, re.IGNORECASE,
        )
        if inline:
            visitor_name = inline.group(1).strip().title()
            update_session(session_id, {
                "visitor_name": visitor_name,
                "stage": "ready",
                "needs_contact_after": True,
            })
            stage = "ready"
        elif _looks_like_name(user_message):
            visitor_name = user_message.strip().title()
            update_session(session_id, {
                "visitor_name": visitor_name,
                "stage": "collect_phone",
            })
            response = (
                f"Nice to meet you, {visitor_name}! "
                "Could I get your phone number? "
                "We'll use it to send booking confirmations."
            )
            add_turn(session_id, user_message, response)
            return response
        else:
            update_session(session_id, {"stage": "ready", "needs_name_after": True})
            stage = "ready"

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE: COLLECT PHONE
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "collect_phone":
        txt = user_message.strip()
        if _valid_phone(txt):
            update_session(session_id, {
                "visitor_phone": txt,
                "visitor_contact": txt,
                "stage": "collect_email",
            })
            response = (
                "Got it! And your email address? "
                "We'll send your booking confirmation there too."
            )
        else:
            response = (
                "That doesn't look like a valid phone number. "
                "Could you re-enter it? (e.g. +971 50 123 4567)"
            )
        add_turn(session_id, user_message, response)
        return response

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE: COLLECT EMAIL
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "collect_email":
        txt = user_message.strip()
        if _valid_email(txt):
            visitor_name = session.get("visitor_name", "")
            update_session(session_id, {
                "visitor_email": txt,
                "stage": "ready",
            })
            _save_visitor(visitor_name, session.get("visitor_phone", txt))
            response = (
                f"Perfect, thank you{', ' + visitor_name if visitor_name else ''}! "
                "I'm all set. How can I help — would you like to book an appointment, "
                "check availability, or ask about our services?"
            )
        elif txt.lower() in ("skip", "no", "no thanks", "later"):
            update_session(session_id, {"stage": "ready"})
            response = (
                "No problem! How can I help — would you like to book an appointment, "
                "check availability, or ask about our services?"
            )
        else:
            response = (
                "That doesn't look like a valid email. "
                "Could you re-enter it? Or type 'skip' to continue without one."
            )
        add_turn(session_id, user_message, response)
        return response

    # ─────────────────────────────────────────────────────────────────────────
    # FIX 1: STAGE awaiting_consultation_confirm — intercept BEFORE classify_intent
    # This stage fires when a T2 service gate returned NEEDS_CONSULTATION and we
    # asked the user "would you like to book a free consultation?". We must handle
    # yes/no here regardless of what the intent classifier returns for "yes".
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "awaiting_consultation_confirm":
        if _is_yes(user_message):
            spmu_service_id = session.get("pending_consultation_service_id")
            branch_id = session.get("pending_consultation_branch_id")
            service_name = session.get("last_service_name", "this service")
            response = _book_consultation_slots(
                session_id, spmu_service_id, branch_id, service_name,
                user_message, history,
            )
            add_turn(session_id, user_message, response)
            return response

        elif _is_no(user_message):
            update_session(session_id, {"stage": "ready"})
            response = "No problem at all — is there anything else I can help you with?"
            add_turn(session_id, user_message, response)
            return response

        else:
            response = "Would you like to book a free consultation? Just say yes or no."
            add_turn(session_id, user_message, response)
            return response

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE: USER PICKING A CONSULTATION SLOT (T2)
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "awaiting_consultation_slots":
        slots = session.get("pending_slots", [])
        choice = _parse_slot_choice(user_message, len(slots))

        if choice == -1:
            context = f"User gave an invalid slot choice. There are {len(slots)} options numbered 1 to {len(slots)}. Ask them again naturally."
            response = _generate_response(context, user_message, history)
            add_turn(session_id, user_message, response)
            return response
        if choice is None:
            context = f"User gave an out-of-range slot choice. There are {len(slots)} options numbered 1 to {len(slots)}. Ask them again naturally."
            response = _generate_response(context, user_message, history)
            add_turn(session_id, user_message, response)
            return response

        selected = slots[choice]
        service_id = session.get("pending_consultation_service_id")
        branch_id = (
            session.get("pending_consultation_branch_id")
            or selected.get("branch_id")
            or (selected.get("branches", {}) or {}).get("id")
        )

        if not session.get("visitor_contact") and not session.get("client_id"):
            update_session(session_id, {"pending_slot": selected})
            if not session.get("visitor_name"):
                update_session(session_id, {"stage": "collect_name_for_consultation"})
                response = "Before I confirm — could I get your name please?"
            else:
                update_session(session_id, {"stage": "collect_contact_for_consultation"})
                response = (
                    f"Almost there! Could I get your phone number or email "
                    "so we can send your consultation confirmation?"
                )
            add_turn(session_id, user_message, response)
            return response

        booking = create_booking(
            service_id=service_id,
            slot_id=selected["id"],
            branch_id=branch_id,
            client_id=session.get("client_id"),
            visitor_name=session.get("visitor_name"),
            visitor_contact=session.get("visitor_contact"),
            booking_type="consultation",
        )
        update_session(session_id, {
            "stage": "ready",
            "pending_slots": [],
            "pending_consultation_service_id": None,
            "pending_consultation_branch_id": None,
            "last_booking_ref": booking.get("booking_ref"),
        })
        add_turn(session_id, user_message, booking["message"])
        return booking["message"]

    # ─────────────────────────────────────────────────────────────────────────
    # STAGES: MID-FLOW NAME/CONTACT COLLECTION (consultation)
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "collect_name_for_consultation":
        visitor_name = user_message.strip().title()
        update_session(session_id, {
            "visitor_name": visitor_name,
            "stage": "collect_contact_for_consultation",
        })
        response = (
            f"Thanks, {visitor_name}! And your phone number or email "
            "for the booking confirmation?"
        )
        add_turn(session_id, user_message, response)
        return response

    if stage == "collect_contact_for_consultation":
        contact = user_message.strip()
        if not _valid_phone(contact) and not _valid_email(contact):
            response = (
                "Please enter a valid phone number or email address "
                "so we can send the confirmation."
            )
            add_turn(session_id, user_message, response)
            return response

        update_session(session_id, {"visitor_contact": contact})
        _save_visitor(session.get("visitor_name", ""), contact)
        selected = session.get("pending_slot")
        service_id = session.get("pending_consultation_service_id")
        branch_id = (
            session.get("pending_consultation_branch_id")
            or (selected.get("branch_id") if selected else None)
            or ((selected.get("branches", {}) or {}).get("id") if selected else None)
        )

        if not selected or not service_id:
            update_session(session_id, {"stage": "ready"})
            response = (
                "Sorry, I lost track of that slot — "
                "which service were you interested in a consultation for?"
            )
            add_turn(session_id, user_message, response)
            return response

        booking = create_booking(
            service_id=service_id,
            slot_id=selected["id"],
            branch_id=branch_id,
            visitor_name=session.get("visitor_name"),
            visitor_contact=contact,
            booking_type="consultation",
        )
        update_session(session_id, {
            "stage": "ready",
            "pending_slot": None,
            "pending_slots": [],
            "pending_consultation_service_id": None,
            "pending_consultation_branch_id": None,
            "last_booking_ref": booking.get("booking_ref"),
        })
        add_turn(session_id, user_message, booking["message"])
        return booking["message"]

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE: USER SELECTING A REGULAR SERVICE SLOT
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "awaiting_slot_selection":
        slots = session.get("pending_slots", [])
        choice = _parse_slot_choice(user_message, len(slots))

        if choice == -1:
            context = f"User gave an invalid slot choice. There are {len(slots)} options numbered 1 to {len(slots)}. Ask them again naturally."
            response = _generate_response(context, user_message, history)
            add_turn(session_id, user_message, response)
            return response
        if choice is None:
            context = f"User gave an out-of-range slot choice. There are {len(slots)} options numbered 1 to {len(slots)}. Ask them again naturally."
            response = _generate_response(context, user_message, history)
            add_turn(session_id, user_message, response)
            return response

        selected = slots[choice]
        service_id = session.get("last_service_id")
        service_name = session.get("last_service_name", "")
        branch_id = (
            session.get("last_branch_id")
            or selected.get("branch_id")
            or (selected.get("branches", {}) or {}).get("id")
        )

        try:
            svc = (
                supabase.table("services")
                .select("name, price_aed, service_tier")
                .eq("id", service_id)
                .single()
                .execute()
                .data
            )
        except Exception:
            svc = {"name": service_name, "price_aed": 0, "service_tier": "T1"}

        try:
            DUBAI_TZ = timezone(timedelta(hours=4))
            dt = datetime.fromisoformat(selected["start_time"].replace("Z", "+00:00"))
            dt_dubai = dt.astimezone(DUBAI_TZ)
            formatted_time = dt_dubai.strftime("%A, %d %B at %I:%M %p")
        except Exception:
            formatted_time = selected.get("start_time", "")[:16]

        branch_name = (
            selected.get("branches", {}).get("name", "our branch")
            if isinstance(selected.get("branches"), dict)
            else "our branch"
        )

        update_session(session_id, {
            "pending_slot": selected,
            "pending_service": svc,
            "last_branch_id": branch_id,
            "stage": "awaiting_confirmation",
        })

        context = (
            f"Booking summary to confirm with user:\n"
            f"Service: {svc['name']}\n"
            f"Branch: {branch_name}\n"
            f"Date & Time: {formatted_time}\n"
            f"Price: AED {svc['price_aed']:.0f}\n\n"
            "Present this summary naturally and ask if they'd like to confirm."
        )
        response = _generate_response(context, user_message, history)
        add_turn(session_id, user_message, response)
        return response

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE: AWAITING FINAL BOOKING CONFIRMATION (yes/no)
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "awaiting_confirmation":
        if _is_yes(user_message):
            slot = session.get("pending_slot")
            service_id = session.get("last_service_id")
            branch_id = session.get("last_branch_id") or (slot.get("branch_id") if slot else None)

            if not session.get("visitor_contact") and not session.get("client_id"):
                update_session(session_id, {"stage": "collect_name_for_booking"
                    if not session.get("visitor_name") else "collect_contact_for_booking"})
                if not session.get("visitor_name"):
                    response = "Before I confirm — could I get your name please?"
                else:
                    response = (
                        "Almost done! I just need your phone number or email "
                        "to send the confirmation to."
                    )
                add_turn(session_id, user_message, response)
                return response

            booking = create_booking(
                service_id=service_id,
                slot_id=slot["id"],
                branch_id=branch_id,
                client_id=session.get("client_id"),
                visitor_name=session.get("visitor_name"),
                visitor_contact=session.get("visitor_contact"),
            )
            update_session(session_id, {
                "stage": "ready",
                "pending_slot": None,
                "pending_slots": [],
                "pending_service": None,
                "last_booking_ref": booking.get("booking_ref"),
            })
            add_turn(session_id, user_message, booking["message"])
            return booking["message"]

        elif _is_no(user_message):
            update_session(session_id, {
                "stage": "ready",
                "pending_slot": None,
                "pending_slots": [],
                "pending_service": None,
            })
            response = "No problem — is there anything else I can help you with?"
            add_turn(session_id, user_message, response)
            return response

        else:
            svc = session.get("pending_service", {})
            context = f"User gave an unclear response. Ask them again whether they want to confirm the {svc.get('name', 'booking')} — keep it natural."
            response = _generate_response(context, user_message, history)
            add_turn(session_id, user_message, response)
            return response

    # ─────────────────────────────────────────────────────────────────────────
    # MID-BOOKING NAME/CONTACT COLLECTION (regular booking)
    # ─────────────────────────────────────────────────────────────────────────
    if stage == "collect_name_for_booking":
        visitor_name = user_message.strip().title()
        update_session(session_id, {
            "visitor_name": visitor_name,
            "stage": "collect_contact_for_booking",
        })
        response = f"Thanks, {visitor_name}! And your phone number or email?"
        add_turn(session_id, user_message, response)
        return response

    if stage == "collect_contact_for_booking":
        contact = user_message.strip()
        if not _valid_phone(contact) and not _valid_email(contact):
            response = (
                "Please enter a valid phone number or email address "
                "so we can send the booking confirmation."
            )
            add_turn(session_id, user_message, response)
            return response

        update_session(session_id, {"visitor_contact": contact})
        _save_visitor(session.get("visitor_name", ""), contact)

        slot = session.get("pending_slot")
        service_id = session.get("last_service_id")
        branch_id = session.get("last_branch_id") or (slot.get("branch_id") if slot else None)

        if not slot or not service_id:
            update_session(session_id, {"stage": "ready"})
            response = "Sorry, I lost track of that slot — which service would you like to book?"
            add_turn(session_id, user_message, response)
            return response

        booking = create_booking(
            service_id=service_id,
            slot_id=slot["id"],
            branch_id=branch_id,
            visitor_name=session.get("visitor_name"),
            visitor_contact=contact,
        )
        update_session(session_id, {
            "stage": "ready",
            "pending_slot": None,
            "pending_slots": [],
            "pending_service": None,
            "last_booking_ref": booking.get("booking_ref"),
        })
        add_turn(session_id, user_message, booking["message"])
        return booking["message"]

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE: READY — full intent classification + routing
    # NOTE: All stage-specific handlers above return early, so we only reach
    # here when stage is genuinely "ready". The old "FIX C" re-read block has
    # been removed — awaiting_consultation_confirm is now handled above before
    # classify_intent is ever called.
    # ─────────────────────────────────────────────────────────────────────────

    classification = classify_intent(user_message, history)
    intent = classification["intent"]
    entities = classification["entities"]
    confidence = classification["confidence"]
    update_session(session_id, {"last_intent": intent})

    # ── Low confidence → ask for clarification ────────────────────────────
    if confidence < 0.55 and intent not in ("greeting_smalltalk", "escalate_human"):
        response = (
            f"I want to make sure I help you with the right thing"
            f"{', ' + name if name else ''}. "
            "Could you tell me a bit more — which treatment are you interested in, "
            "or what would you like to do?"
        )
        add_turn(session_id, user_message, response)
        return response

    # ── Greeting ────────────────────────────────────────────────────────────
    if intent == "greeting_smalltalk":
        if name:
            greeting_context = f"The user's name is {name}. Welcome them back warmly."
        else:
            greeting_context = (
                "This is a new visitor. Welcome them warmly and introduce Luma. "
                "Then ask for their name to get started."
            )
        response = _generate_response(greeting_context, user_message, history)
        if not name:
            update_session(session_id, {"stage": "collect_name"})
        add_turn(session_id, user_message, response)
        return response

    # ── FAQ ──────────────────────────────────────────────────────────────────
    if intent == "faq_general":
        result = lookup_faq(user_message, conversation_context=history[-6:])
        response = _generate_response(result["answer"], user_message, history)
        add_turn(session_id, user_message, response)
        return response

    # ── Escalate ─────────────────────────────────────────────────────────────
    if intent == "escalate_human":
        from api.escalation import escalate_to_human
        result = escalate_to_human(session_id, reason="user_requested")
        add_turn(session_id, user_message, result["message"])
        return result["message"]

    # ── Check availability / Create booking ──────────────────────────────────
    if intent in ("check_availability", "create_booking"):
        service_name_raw = entities.get("service", "")

        # FIX 2: Fall back to last known service if entity extraction came up empty.
        # This handles "book it", "yes please", "both" etc. after prior context.
        service_id = resolve_service_id(service_name_raw) if service_name_raw else None
        if not service_id:
            service_id = session.get("last_service_id")
            service_name_raw = session.get("last_service_name", "")

        if not service_id:
            context = (
                f"The user said '{user_message}' but I couldn't identify a specific service. "
                "Ask them naturally which treatment they're interested in. "
                "If they mentioned something we don't offer like a haircut, "
                "acknowledge it and explain what we do specialise in."
            )
            response = _generate_response(context, user_message, history)
            add_turn(session_id, user_message, response)
            return response

        try:
            svc_row = (
                supabase.table("services")
                .select("name, service_tier, price_aed, category")
                .eq("id", service_id)
                .single()
                .execute()
                .data
            )
            service_name = svc_row["name"]
        except Exception:
            service_name = service_name_raw.title() if service_name_raw else "this service"
            svc_row = {"service_tier": "T1"}

        update_session(session_id, {
            "last_service_id": service_id,
            "last_service_name": service_name,
        })

        if entities.get("branch"):
            branch_id = resolve_branch_id(entities["branch"])
            if branch_id:
                update_session(session_id, {"last_branch_id": branch_id})

        gate = check_service_gate(service_id, session.get("client_id"))

        if gate["status"] == "CLEAR":
            response = _run_availability_and_show_slots(
                session_id=session_id,
                service_id=service_id,
                service_name=service_name,
                entities=entities,
                user_message=user_message,
                history=history,
            )

        elif gate["status"] in ("NEEDS_CONSULTATION", "CLEARANCE_EXPIRED"):
            update_session(session_id, {
                "pending_consultation_service_id": service_id,
                "pending_consultation_branch_id": session.get("last_branch_id"),
                "stage": "awaiting_consultation_confirm",
            })
            response = _generate_response(gate["message"], user_message, history)

        elif gate["status"] == "NEEDS_SCREENING":
            if _is_yes(user_message) or intent == "create_booking":
                update_session(session_id, {
                    "screening_service_id": service_id,
                    "screening_service_category": svc_row.get("category", ""),
                    "screening_answers": {},
                    "stage": "ready",
                })
                first_q = SCREENING_QUESTIONS[0]
                response = (
                    f"{gate['message']}\n\n"
                    f"Question 1 of {len(SCREENING_QUESTIONS)}: {first_q['question']}"
                )
            else:
                response = _generate_response(gate["message"], user_message, history)

        elif gate["status"] == "SCREENING_PENDING":
            response = _generate_response(gate["message"], user_message, history)

        elif gate["status"] == "HARD_BLOCK":
            response = _generate_response(gate["message"], user_message, history)

        else:
            response = _generate_response(
                "Unable to check service requirements right now. "
                "Please call the branch directly.",
                user_message, history,
            )

        add_turn(session_id, user_message, response)
        return response

    # ── FIX 3: book_consultation intent — use pending session context if no entity ──
    # Previously this fell through to "which service?" when user said "yes" to a
    # consultation offer, because entities.service was empty. Now we check session first.
    if intent == "book_consultation":
        service_name_raw = entities.get("service", "")
        service_id = resolve_service_id(service_name_raw) if service_name_raw else None
        branch_id = None
        if entities.get("branch"):
            branch_id = resolve_branch_id(entities["branch"])

        # Fall back to whatever T2 service we were discussing
        if not service_id:
            service_id = session.get("pending_consultation_service_id") or session.get("last_service_id")
            branch_id = branch_id or session.get("pending_consultation_branch_id") or session.get("last_branch_id")
            service_name_raw = session.get("last_service_name", "")

        if not service_id:
            response = (
                "Which service would you like to book a consultation for? "
                "(e.g. brow SPMU, lip blush, nano brows)"
            )
            add_turn(session_id, user_message, response)
            return response

        update_session(session_id, {
            "pending_consultation_service_id": service_id,
            "pending_consultation_branch_id": branch_id,
            "last_service_id": service_id,
            "last_service_name": service_name_raw.title() if service_name_raw else session.get("last_service_name", ""),
        })

        response = _book_consultation_slots(
            session_id, service_id, branch_id,
            session.get("last_service_name", service_name_raw.title()),
            user_message, history,
        )
        add_turn(session_id, user_message, response)
        return response

    # ── Check clearance status ────────────────────────────────────────────────
    if intent == "check_clearance_status":
        client_id = session.get("client_id")
        service_name_raw = entities.get("service", "")
        service_id = resolve_service_id(service_name_raw) if service_name_raw else None

        if not client_id:
            response = (
                "Clearance records are linked to your client profile. "
                "If you're a returning client, please let me know and I'll pull up your records."
            )
        elif service_id:
            gate = check_service_gate(service_id, client_id)
            msg = gate.get("message") or f"Your clearance for {service_name_raw} is valid — you're good to book."
            response = _generate_response(msg, user_message, history)
        else:
            response = (
                "Which service's clearance would you like to check? "
                "(e.g. brow SPMU, lip filler)"
            )
        add_turn(session_id, user_message, response)
        return response

    # ── Check frequency ───────────────────────────────────────────────────────
    if intent == "check_frequency":
        client_id = session.get("client_id")
        service_name_raw = entities.get("service", "")

        if not client_id:
            response = (
                "Frequency checks are based on your booking history, "
                "which is linked to your client profile. "
                "Are you an existing client?"
            )
        else:
            service_id = resolve_service_id(service_name_raw) if service_name_raw else None
            if service_id:
                gate = check_service_gate(service_id, client_id)
                if gate["status"] == "HARD_BLOCK":
                    response = _generate_response(gate["message"], user_message, history)
                else:
                    response = _generate_response(
                        f"You can rebook {service_name_raw} — "
                        "no frequency block is active on your account.",
                        user_message, history,
                    )
            else:
                response = "Which service would you like to check the rebooking interval for?"
        add_turn(session_id, user_message, response)
        return response

    # ── Modify booking ────────────────────────────────────────────────────────
    if intent == "modify_booking":
        client_id = session.get("client_id")
        if not client_id:
            response = (
                "Booking modifications are available to authenticated clients. "
                "Please call the branch directly to make any changes, "
                "or I can escalate to a team member now if you'd like."
            )
        else:
            booking_ref = entities.get("booking_ref") or session.get("last_booking_ref")
            if booking_ref:
                response = _generate_response(
                    f"Client wants to modify booking {booking_ref}. "
                    "Direct them to call the branch or connect them with the team.",
                    user_message, history,
                )
            else:
                response = (
                    "Which booking would you like to change? "
                    "Please share your booking reference (e.g. BKG-2026-XXXX)."
                )
        add_turn(session_id, user_message, response)
        return response

    # ── Cancel booking ────────────────────────────────────────────────────────
    if intent == "cancel_booking":
        client_id = session.get("client_id")
        if not client_id:
            response = (
                "Cancellations can be made by calling the branch directly "
                "or I can connect you with a team member now. "
                "Would you like me to do that?"
            )
        else:
            booking_ref = entities.get("booking_ref") or session.get("last_booking_ref")
            if booking_ref:
                try:
                    supabase.table("bookings").update(
                        {"status": "cancelled", "updated_at": datetime.now(timezone.utc).isoformat()}
                    ).eq("id", booking_ref).eq("client_id", client_id).execute()
                    response = _generate_response(
                        f"Booking {booking_ref} has been cancelled successfully.",
                        user_message, history,
                    )
                except Exception as e:
                    response = _generate_response(
                        "Unable to cancel the booking right now. "
                        "Please call the branch directly.",
                        user_message, history,
                    )
            else:
                response = (
                    "Which booking would you like to cancel? "
                    "Please share the booking reference (e.g. BKG-2026-XXXX)."
                )
        add_turn(session_id, user_message, response)
        return response

    # ── Add notes ─────────────────────────────────────────────────────────────
    if intent == "add_notes":
        notes_text = entities.get("notes", user_message)
        booking_ref = entities.get("booking_ref") or session.get("last_booking_ref")
        if booking_ref and notes_text:
            try:
                supabase.table("bookings").update(
                    {
                        "notes": notes_text,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).eq("id", booking_ref).execute()
                response = _generate_response(
                    f"Note added to booking {booking_ref}: '{notes_text}'.",
                    user_message, history,
                )
            except Exception:
                response = _generate_response(
                    "I wasn't able to add the note right now. "
                    "Please call the branch and they'll add it for you.",
                    user_message, history,
                )
        else:
            response = (
                "Which booking would you like to add a note to? "
                "Please share the booking reference and your note."
            )
        add_turn(session_id, user_message, response)
        return response

    # ── Initiate payment ──────────────────────────────────────────────────────
    if intent == "initiate_payment":
        booking_ref = entities.get("booking_ref") or session.get("last_booking_ref")
        if booking_ref:
            try:
                result = (
                    supabase.table("bookings")
                    .select("id, payment_link, deposit_amount_aed, payment_status")
                    .eq("id", booking_ref)
                    .single()
                    .execute()
                )
                bk = result.data
                if bk and bk.get("payment_link"):
                    response = _generate_response(
                        f"Payment link for {booking_ref}:\n"
                        f"Amount: AED {bk['deposit_amount_aed']:.0f}\n"
                        f"Link: {bk['payment_link']}\n"
                        "(Valid for 24 hours)",
                        user_message, history,
                    )
                else:
                    response = _generate_response(
                        f"No payment link found for {booking_ref}. "
                        "This booking may already be paid, or doesn't require payment.",
                        user_message, history,
                    )
            except Exception:
                response = _generate_response(
                    "Unable to retrieve the payment link right now. "
                    "Please call the branch directly.",
                    user_message, history,
                )
        else:
            response = (
                "Which booking would you like the payment link for? "
                "Please share your booking reference (e.g. BKG-2026-XXXX)."
            )
        add_turn(session_id, user_message, response)
        return response

    # ── Fallback ──────────────────────────────────────────────────────────────
    faq_result = lookup_faq(user_message, conversation_context=history[-6:])
    if faq_result["status"] == "FOUND":
        response = _generate_response(faq_result["answer"], user_message, history)
    else:
        response = _generate_response(
            "I'm not sure how to help with that. "
            "I can help you book an appointment, check availability, "
            "answer questions about our services, or connect you with the team.",
            user_message, history,
        )

    # ── Post-turn: ask for name/contact if deferred ───────────────────────────
    if session.get("needs_name_after"):
        update_session(session_id, {"needs_name_after": False})
        response += f"\n\nBy the way — may I have your name? I'd love to personalise your experience."
        update_session(session_id, {"stage": "collect_name"})
    elif session.get("needs_contact_after"):
        update_session(session_id, {"needs_contact_after": False})
        response += "\n\nCould I also grab your phone number to send booking updates?"
        update_session(session_id, {"stage": "collect_phone"})

    add_turn(session_id, user_message, response)
    return response