import os
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from api.agent_controller import handle_message
from api.memory import get_session, set_client, update_session
from api.database import supabase

load_dotenv()

app = FastAPI(title="Booking Concierge Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    client_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()

    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())

    # If client_id passed, upgrade session to client tier
    if request.client_id:
        set_client(session_id, request.client_id)

    # Handle the message
    response_text = handle_message(session_id, request.message)

    # Log to Supabase
    session = get_session(session_id)
    latency_ms = int((time.time() - start_time) * 1000)

    try:
        # Ensure session exists in Supabase
        supabase.table("sessions").upsert({
            "id": session_id,
            "channel": "web",
            "user_tier": session.get("user_tier", "visitor"),
            "client_id": session.get("client_id"),
            "status": session.get("status", "active"),
            "last_intent": session.get("last_intent"),
            "last_booking_ref": session.get("last_booking_ref"),
        }).execute()

        # Log the turn
        supabase.table("agent_logs").insert({
            "session_id": session_id,
            "turn": session.get("turn", 1),
            "channel": "web",
            "user_message": request.message,
            "intent": session.get("last_intent"),
            "tool_called": session.get("last_intent"),
            "agent_response": response_text,
            "latency_ms": latency_ms,
            "escalated": session.get("status") == "escalated",
        }).execute()
    except Exception as e:
        print(f"Logging error (non-fatal): {e}")

    return ChatResponse(response=response_text, session_id=session_id)


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    # Stubbed — WhatsApp channel not wired up for prototype
    return {"status": "stub", "message": "WhatsApp channel not active in prototype"}


# Serve chat widget if it exists
if os.path.exists("web"):
    app.mount("/web", StaticFiles(directory="web"), name="web")

@app.get("/")
def root():
    index = "web/index.html"
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Booking Concierge Agent is running. POST to /chat to interact."}