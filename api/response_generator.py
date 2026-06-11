import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are a friendly, professional booking assistant for a luxury beauty and wellness brand in Dubai.
Your name is Luma. You help clients book appointments, answer questions, and guide them through the booking process.

Rules:
- Keep responses concise — maximum 4 sentences unless showing a booking summary
- Be warm and professional, never robotic
- Never make up availability or prices — only use the information provided to you
- If you have a tool result, base your response entirely on it
- Never mention system errors directly — say "I wasn't able to fetch that just now"
- Use "we" and "our" when referring to the brand
"""


def generate_response(tool_result: str, user_message: str, history: list = []) -> str:
    """
    Generates a branded conversational response using GPT-4o.
    Falls back to the raw tool result if the API call fails.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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
    except Exception as e:
        print(f"[RESPONSE GENERATOR] Error: {e}")
        return tool_result