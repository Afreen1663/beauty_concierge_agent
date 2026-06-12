"""
intent_classifier.py — LLM-powered intent and entity extraction.

Uses GPT-4o with a structured JSON prompt to classify the user's intent
and extract relevant booking entities from each message. Includes
confidence scoring and conversation history for context.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VALID_INTENTS = [
    "check_availability",
    "create_booking",
    "modify_booking",
    "cancel_booking",
    "add_notes",
    "initiate_payment",
    "faq_general",
    "escalate_human",
    "greeting_smalltalk",
    "book_consultation",
    "check_clearance_status",
    "check_frequency",
]

SYSTEM_PROMPT = """You are an intent classifier for Luma — a luxury beauty and wellness booking assistant in Dubai.

Classify the user's message and return ONLY a JSON object with these exact fields:
- "intent": one string value from the valid intents list
- "entities": an object containing any extracted entities (may be empty {})
- "confidence": a float between 0.0 and 1.0

Valid intents:
- check_availability    — user wants to see open slots for a service, date, branch, or artist
- create_booking        — user wants to book / confirm an appointment
- modify_booking        — user wants to change date, time, service, or artist on an existing booking
- cancel_booking        — user wants to cancel an existing booking
- add_notes             — user wants to add a preference or note to a booking
- initiate_payment      — user wants a payment link or wants to pay
- faq_general           — general question about prices, hours, location, policy, aftercare, etc.
- escalate_human        — user wants to speak to a person / receptionist
- greeting_smalltalk    — hello, hi, good morning, casual opener, or small talk only
- book_consultation     — user wants to book a free consultation or patch test
- check_clearance_status — user wants to know if their clearance / patch test is on file
- check_frequency       — user wants to know if they can rebook a treatment soon

Entity fields to extract if present:
- service   : treatment name (e.g. "brow lamination", "lip filler", "anti-wrinkle injections")
- branch    : location name (e.g. "Dubai Mall", "JBR", "Marina")
- date      : date string as-is (e.g. "tomorrow", "Saturday", "5 July") — do NOT convert to ISO
- time      : time string as-is (e.g. "2pm", "after 5", "morning")
- artist    : artist or therapist name if mentioned
- notes     : any preferences or special requests mentioned
- booking_ref : booking reference if mentioned (e.g. "BKG-2026-A3X9")

Classification rules:
- Return ONLY valid JSON. No markdown. No explanation. No extra text.
- Greetings (hi, hello, hey, good morning, start) → greeting_smalltalk, confidence 0.95+
- A bare "yes", "yeah", "sure", "ok", "okay", "no", "nope", "nah" with no other content → greeting_smalltalk, confidence 0.90 (stage machine handles these; don't route to booking intents)
- If the user mentions a T2 service (SPMU, brow SPMU, lip blush, nano brows, eyeliner SPMU) AND wants to book → create_booking (gating is handled by the controller, not here)
- If the user mentions a T3 service (anti-wrinkle, lip filler, thread lift, laser, chemical peel, filler, botox, injectables, hydrafacial) AND wants to book → create_booking
- "check if there's a slot AND book it" → create_booking (multi-intent resolved as booking)
- If confidence < 0.60 use faq_general as fallback, NOT escalate_human
- escalate_human only when user explicitly says "speak to someone", "talk to a person", "human agent", etc.


Examples:
{"intent":"greeting_smalltalk","entities":{},"confidence":0.97}
{"intent":"check_availability","entities":{"service":"brow lamination","date":"Saturday"},"confidence":0.93}
{"intent":"create_booking","entities":{"service":"lip filler","branch":"Dubai Mall"},"confidence":0.88}
{"intent":"faq_general","entities":{},"confidence":0.82}
{"intent":"escalate_human","entities":{},"confidence":0.95}
"""


def classify_intent(message: str, conversation_history: list = None) -> dict:
    """
    Classifies the user message and returns:
    { intent: str, entities: dict, confidence: float }
    """
    if conversation_history is None:
        conversation_history = []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Last 4 turns for context
    for turn in conversation_history[-8:]:
        messages.append(turn)

    messages.append({"role": "user", "content": message})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)

        intent = result.get("intent", "faq_general")
        if intent not in VALID_INTENTS:
            intent = "faq_general"
            result["confidence"] = 0.4

        return {
            "intent": intent,
            "entities": result.get("entities", {}),
            "confidence": float(result.get("confidence", 0.5)),
        }

    except json.JSONDecodeError:
        return {"intent": "faq_general", "entities": {}, "confidence": 0.3}
    except Exception as e:
        print(f"[INTENT CLASSIFIER] Error: {e}")
        return {"intent": "faq_general", "entities": {}, "confidence": 0.3}