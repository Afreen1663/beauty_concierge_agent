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

SYSTEM_PROMPT = """You are an intent classifier for a beauty and wellness booking assistant in Dubai.

Your job is to read the user's message and return a JSON object with exactly these fields:
- intent: one of the valid intents listed below
- entities: an object with any of these fields if found: service, branch, date, time, artist, notes
- confidence: a number between 0.0 and 1.0

Valid intents:
- check_availability: user wants to know what slots are open
- create_booking: user wants to book an appointment
- modify_booking: user wants to change an existing booking
- cancel_booking: user wants to cancel a booking
- add_notes: user wants to add a note or preference to a booking
- initiate_payment: user wants to pay for a booking
- faq_general: user is asking a general question (hours, price, location, policy)
- escalate_human: user wants to speak to a person
- greeting_smalltalk: user is just saying hello or chatting
- book_consultation: user wants to book a free consultation
- check_clearance_status: user wants to know if their clearance is on file
- check_frequency: user wants to know if they can rebook a treatment

Rules:
- Return ONLY valid JSON. No explanation. No markdown. No extra text.
- If unsure, choose the closest intent and set confidence below 0.6
- For dates like "tomorrow", "Saturday", "next week" — keep them as-is in the entities (do not convert)
- If no entity is found for a field, omit that field from entities

Example output:
{"intent": "check_availability", "entities": {"service": "brow lamination", "date": "Saturday"}, "confidence": 0.92}
"""

def classify_intent(message: str, conversation_history: list = []) -> dict:
    """
    Takes a user message and returns intent, entities, and confidence.
    Returns a dict: { intent, entities, confidence }
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Include last 4 turns of history for context
    for turn in conversation_history[-4:]:
        messages.append(turn)

    messages.append({"role": "user", "content": message})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0,
            max_tokens=200,
        )

        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)

        # Validate intent is one we know
        if result.get("intent") not in VALID_INTENTS:
            result["intent"] = "faq_general"
            result["confidence"] = 0.4

        return {
            "intent": result.get("intent", "faq_general"),
            "entities": result.get("entities", {}),
            "confidence": float(result.get("confidence", 0.5)),
        }

    except json.JSONDecodeError:
        return {"intent": "faq_general", "entities": {}, "confidence": 0.3}
    except Exception as e:
        print(f"Intent classifier error: {e}")
        return {"intent": "escalate_human", "entities": {}, "confidence": 0.0}