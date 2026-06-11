"""
faq.py — FAQ lookup against Supabase.

Searches the faqs table by keyword match against question and answer fields.
Falls back to GPT with a Luma-branded system prompt when no match is found,
so medical terms, service details, and policies are answered intelligently
instead of deflecting to "call the branch".
"""

import os
from openai import OpenAI
from dotenv import load_dotenv
from api.database import supabase

load_dotenv()
_openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_STOP_WORDS = {
    "what", "when", "where", "how", "does", "your", "have", "that",
    "this", "with", "about", "which", "are", "the", "for", "you",
    "can", "will", "do", "is", "it", "a", "an", "to", "and", "or",
    "in", "on", "at", "of", "my", "i", "me", "we", "our",
}

_FAQ_FALLBACK_SYSTEM_PROMPT = """You are Luma, the booking concierge for a luxury beauty and wellness brand in Dubai.

Your personality:
- Warm, natural, and genuinely helpful — like a knowledgeable friend who works at the salon
- Never robotic, never scripted-sounding
- You acknowledge what the person asked before answering
- When you're unsure of something specific to our business (exact prices, availability), say so honestly and offer to help another way

Your knowledge:
- You can explain beauty and aesthetic treatments naturally (SPMU, fillers, anti-wrinkle injections, HydraFacial, chemical peels, brow and lash services)
- You can explain medical terms that come up in a health screening context (e.g. blood thinners, autoimmune conditions, contraindications)
- You know general best-practice guidance for pre/post treatment care
- You understand what a luxury concierge experience feels like and speak accordingly

Services offered:
- Brow threading, lamination, tint, lash tint, waxing (standard beauty)
- Brow SPMU, lip blush, eyeliner SPMU, nano brows (semi-permanent makeup)
- Anti-wrinkle injections, lip filler, HydraFacial, chemical peel (medical aesthetic)

Rules:
- Keep answers under 4 sentences unless a detailed explanation is genuinely needed
- Plain text only — no markdown, no bullet symbols
- Never invent specific prices or slot availability
- If it's something only our team can confirm (e.g. a specific branch policy), say so warmly and offer to connect them
"""


def _extract_keywords(question: str) -> list[str]:
    """Extracts meaningful keywords from the user's question."""
    words = question.lower().split()
    return [w.strip("?.,!") for w in words if len(w) > 3 and w not in _STOP_WORDS]


def _gpt_fallback(question: str, conversation_context: list = None) -> str:
    """
    Uses GPT-4o with a Luma system prompt to answer questions the FAQ
    database couldn't match. Accepts optional conversation history for context.
    """
    messages = [{"role": "system", "content": _FAQ_FALLBACK_SYSTEM_PROMPT}]

    if conversation_context:
        messages.extend(conversation_context[-6:])

    messages.append({"role": "user", "content": question})

    try:
        response = _openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[FAQ GPT FALLBACK] Error: {e}")
        return (
            "I want to make sure I give you the right answer on that — "
            "our team at either branch will be able to help you straight away."
        )


def lookup_faq(question: str, conversation_context: list = None) -> dict:
    """
    Searches the FAQ table for an answer matching the user's question.

    Strategy:
    1. Extract keywords from the question
    2. Try each keyword against the question column (ilike)
    3. Try each keyword against the answer column (ilike)
    4. If no DB match found, fall back to GPT with a Luma-branded system prompt
       instead of deflecting to "call the branch"

    Args:
        question: The user's raw question string.
        conversation_context: Optional list of recent chat history dicts
                              ({ role, content }) to give GPT context.

    Returns:
        { status: "FOUND"|"GPT_FALLBACK"|"ERROR", answer: str, matched_question: str|None }
    """
    keywords = _extract_keywords(question)

    # No meaningful keywords — go straight to GPT rather than deflecting
    if not keywords:
        return {
            "status": "GPT_FALLBACK",
            "answer": _gpt_fallback(question, conversation_context),
            "matched_question": None,
        }

    try:
        for keyword in keywords:
            # Search in question text
            result = (
                supabase.table("faqs")
                .select("question, answer")
                .ilike("question", f"%{keyword}%")
                .limit(1)
                .execute()
            )
            if result.data:
                return {
                    "status": "FOUND",
                    "answer": result.data[0]["answer"],
                    "matched_question": result.data[0]["question"],
                }

            # Search in answer text
            result = (
                supabase.table("faqs")
                .select("question, answer")
                .ilike("answer", f"%{keyword}%")
                .limit(1)
                .execute()
            )
            if result.data:
                return {
                    "status": "FOUND",
                    "answer": result.data[0]["answer"],
                    "matched_question": result.data[0]["question"],
                }

    except Exception as e:
        print(f"[FAQ] Supabase error: {e}")
        return {
            "status": "ERROR",
            "answer": (
                "I wasn't able to look that up just now. "
                "Please contact the branch directly and the team will help you out."
            ),
            "matched_question": None,
        }

    # No DB match found — use GPT instead of a static deflection
    return {
        "status": "GPT_FALLBACK",
        "answer": _gpt_fallback(question, conversation_context),
        "matched_question": None,
    }