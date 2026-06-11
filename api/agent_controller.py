import os
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timezone

from api.intent_classifier import classify_intent
from api.memory import (
    get_session, update_session, add_turn,
    get_history, clear_screening
)
from api.tools.availability import (
    check_availability, resolve_service_id, resolve_branch_id
)
from api.tools.gate_check import check_service_gate
from api.tools.bookings import create_booking
from api.tools.faq import lookup_faq
from api.tools.screening import (
    get_next_question, parse_yes_no, submit_screening, SCREENING_QUESTIONS
)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


RESPONSE_SYSTEM_PROMPT = """You are a friendly, professional booking assistant for a luxury beauty and wellness brand in Dubai.
Your name is Luma. You help clients book appointments, answer questions, and guide them through the booking process.

Rules:
- Keep responses concise — maximum 4 sentences unless showing a booking summary
- Be warm and professional, never robotic
- Never make up availability or prices — only use the information provided to you
- If you have a tool result, base your response entirely on it
- Never mention system errors directly — say "I wasn't able to fetch that just now"
- Use "we" and "our" when referring to the brand
"""


def generate_response(tool_result: str, user_message: str, history: list) -> str:
    """Uses GPT-4o to generate a branded response based on tool output."""
    messages = [{"role": "system", "content": RESPONSE_SYSTEM_PROMPT}]
    messages.extend(history[-4:])
    messages.append({
        "role": "user",
        "content": f"User said: {user_message}\n\nTool result: {tool_result}\n\nGenerate a response."
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.4,
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return tool_result  # Fall back to raw tool result


def handle_message(session_id: str, user_message: str) -> str:
    """
    Main entry point. Takes a session ID and user message.
    Returns the agent's response string.
    """
    session = get_session(session_id)
    history = get_history(session_id)

    # --- SCREENING IN PROGRESS ---
    # If we're mid-screening, continue collecting answers
    if session.get("screening_answers") is not None and \
       session.get("screening_service_id") and \
       len(session["screening_answers"]) < len(SCREENING_QUESTIONS):

        answers = session["screening_answers"]
        next_q = get_next_question(answers)

        if next_q:
            # We asked a question last turn — parse their answer
            answered_questions = list(answers.keys())
            for q in SCREENING_QUESTIONS:
                if q["id"] not in answered_questions:
                    # This is the question we just asked
                    parsed = parse_yes_no(user_message)
                    if parsed is None:
                        response = f"Sorry, I didn't catch that. Could you just say yes or no? {q['question']}"
                        add_turn(session_id, user_message, response)
                        return response

                    answers[q["id"]] = parsed
                    update_session(session_id, {"screening_answers": answers})

                    # Check if all questions answered
                    next_q = get_next_question(answers)
                    if next_q:
                        response = next_q["question"]
                        add_turn(session_id, user_message, response)
                        return response
                    else:
                        # All done — submit
                        result = submit_screening(
                            service_id=session["screening_service_id"],
                            service_category=session["screening_service_category"],
                            answers=answers,
                            client_id=session.get("client_id"),
                            visitor_name=session.get("visitor_name"),
                            visitor_contact=session.get("visitor_contact"),
                        )
                        clear_screening(session_id)
                        add_turn(session_id, user_message, result["message"])
                        return result["message"]

    # --- NORMAL FLOW ---
    # Step 1: Classify intent
    classification = classify_intent(user_message, history)
    intent = classification["intent"]
    entities = classification["entities"]
    confidence = classification["confidence"]

    update_session(session_id, {"last_intent": intent})

    # Step 2: Low confidence — ask for clarification
    if confidence < 0.60 and intent not in ["greeting_smalltalk", "escalate_human"]:
        response = (
            "I want to make sure I help you with the right thing — "
            "could you give me a bit more detail? For example, which service "
            "are you interested in, or what would you like to do?"
        )
        add_turn(session_id, user_message, response)
        return response

    # Step 3: Route by intent

    # GREETING
    if intent == "greeting_smalltalk":
        response = generate_response(
            "User is greeting. Respond warmly and ask how you can help.",
            user_message, history
        )
        add_turn(session_id, user_message, response)
        return response

    # FAQ
    if intent == "faq_general":
        result = lookup_faq(user_message)
        response = generate_response(result["answer"], user_message, history)
        add_turn(session_id, user_message, response)
        return response

    # ESCALATE
    if intent == "escalate_human":
        response = (
            "Of course — I'll flag this for one of our team members right away. "
            "Someone will be in touch with you shortly. "
            "In the meantime, you're also welcome to call either branch directly."
        )
        update_session(session_id, {"status": "escalated"})
        add_turn(session_id, user_message, response)
        return response

    # STUB INTENTS
    if intent in ["modify_booking", "cancel_booking"]:
        response = (
            "Booking modifications and cancellations need to be handled by our team. "
            "Please contact the branch directly and they'll sort it out for you right away. "
            "Would you like me to escalate this to a team member now?"
        )
        add_turn(session_id, user_message, response)
        return response

    # CHECK AVAILABILITY or CREATE BOOKING
    if intent in ["check_availability", "create_booking", "book_consultation"]:

        # Resolve service
        service_name = entities.get("service") or session.get("last_service_name")
        if not service_name:
            response = "Which service are you interested in? For example, brow threading, brow lamination, or brow SPMU?"
            add_turn(session_id, user_message, response)
            return response

        service_id = resolve_service_id(service_name)
        if not service_id:
            response = f"I couldn't find a service matching '{service_name}'. Could you double-check the name?"
            add_turn(session_id, user_message, response)
            return response

        # Resolve branch
        branch_name = entities.get("branch") or "Dubai Mall"
        branch_id = resolve_branch_id(branch_name)

        # Save to session
        update_session(session_id, {
            "last_service_id": service_id,
            "last_service_name": service_name,
            "last_branch_id": branch_id,
        })

        # Run gate check
        gate = check_service_gate(service_id, session.get("client_id"))

        if gate["status"] == "NEEDS_CONSULTATION":
            # Start consultation booking flow
            avail = check_availability(service_id, branch_id)
            if avail["status"] == "AVAILABLE" and avail["slots"]:
                slot = avail["slots"][0]
                booking = create_booking(
                    service_id=service_id,
                    slot_id=slot["id"],
                    branch_id=branch_id,
                    client_id=session.get("client_id"),
                    visitor_name=session.get("visitor_name"),
                    visitor_contact=session.get("visitor_contact"),
                    booking_type="consultation"
                )
                update_session(session_id, {"last_booking_ref": booking.get("booking_ref")})
                add_turn(session_id, user_message, booking["message"])
                return booking["message"]
            else:
                add_turn(session_id, user_message, gate["message"])
                return gate["message"]

        if gate["status"] in ["CLEARANCE_EXPIRED", "SCREENING_PENDING"]:
            add_turn(session_id, user_message, gate["message"])
            return gate["message"]

        if gate["status"] == "NEEDS_SCREENING":
            # Start screening flow
            update_session(session_id, {
                "screening_service_id": service_id,
                "screening_service_category": gate["service"]["category"],
                "screening_answers": {},
            })
            intro = gate["message"]
            first_q = SCREENING_QUESTIONS[0]["question"]
            response = f"{intro}\n\n{first_q}"
            add_turn(session_id, user_message, response)
            return response

        # Gate cleared — check availability
        if gate["status"] == "CLEAR":
            date_str = entities.get("date") or session.get("last_date")
            avail = check_availability(service_id, branch_id, date_str)

            if avail["status"] == "NO_AVAILABILITY":
                if avail.get("alternatives"):
                    alt_slots = avail["alternatives"]
                    alt_text = "\n".join([
                        f"• {s['start_time'][:10]} at {s.get('branches', {}).get('name', 'our branch')}"
                        for s in alt_slots
                    ])
                    response = (
                        f"There's no availability for that date, but here are the next available slots:\n\n"
                        f"{alt_text}\n\nWould any of these work for you?"
                    )
                else:
                    response = "I'm afraid there's no availability for that service at the moment. Please check back soon or contact the branch directly."
                add_turn(session_id, user_message, response)
                return response

            slots = avail["slots"]

            # If just checking availability
            if intent == "check_availability":
                slot_lines = "\n".join([
                    f"• {s['start_time'][11:16]} at {s.get('branches', {}).get('name', 'our branch')}"
                    for s in slots
                ])
                response = generate_response(
                    f"Available slots for {service_name}:\n{slot_lines}",
                    user_message, history
                )
                update_session(session_id, {
                    "last_slot_id": slots[0]["id"],
                    "last_date": date_str,
                })
                add_turn(session_id, user_message, response)
                return response

            # Create booking with first available slot
            if intent == "create_booking":
                slot = slots[0]
                booking = create_booking(
                    service_id=service_id,
                    slot_id=slot["id"],
                    branch_id=branch_id,
                    client_id=session.get("client_id"),
                    visitor_name=session.get("visitor_name"),
                    visitor_contact=session.get("visitor_contact"),
                )
                update_session(session_id, {"last_booking_ref": booking.get("booking_ref")})
                add_turn(session_id, user_message, booking["message"])
                return booking["message"]

    # FALLBACK
    response = (
        "I'm not quite sure how to help with that. "
        "I can help you check availability, book appointments, or answer questions about our services. "
        "What would you like to do?"
    )
    add_turn(session_id, user_message, response)
    return response