"""
main.py — FastAPI application entry point for the Luma booking concierge.

Exposes:
  GET  /health             — server health check
  POST /chat               — main web chat endpoint
  POST /whatsapp           — WhatsApp webhook (stubbed, architecture-ready)
  GET  /                   — serves the web chat UI (web/index.html if present)

All requests are processed by handle_message() in agent_controller.py.
Sessions are created automatically on first contact.
"""

import os
import time
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv

from api.agent_controller import handle_message
from api.memory import get_session, set_client, update_session
from api.database import supabase

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("luma")


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    client_id: str | None = None
    channel: str = "web"

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty")
        return v


class ChatResponse(BaseModel):
    response: str
    session_id: str


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# APP FACTORY
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Luma Booking Concierge starting up...")
    yield
    log.info("Luma Booking Concierge shutting down.")


app = FastAPI(
    title="Luma Booking Concierge",
    description="AI-powered beauty and wellness booking assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())

    # Upgrade to client tier if client_id provided
    if request.client_id:
        set_client(session_id, request.client_id)

    try:
        response_text = handle_message(session_id, request.message)
    except Exception as e:
        log.error(f"handle_message error for session {session_id[:8]}: {e}", exc_info=True)
        response_text = (
            "I'm sorry, something went wrong on my end. "
            "Please try again, or call either branch directly."
        )

    latency_ms = int((time.time() - start_time) * 1000)
    session = get_session(session_id)

    # Persist session + log turn to Supabase (non-fatal)
    _log_turn_to_supabase(
        session_id=session_id,
        session=session,
        user_message=request.message,
        response_text=response_text,
        latency_ms=latency_ms,
        channel=request.channel,
    )

    log.info(
        f"[{session_id[:8]}] turn={session.get('turn', '?')} "
        f"intent={session.get('last_intent', '?')} "
        f"latency={latency_ms}ms"
    )

    return ChatResponse(response=response_text, session_id=session_id)


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    WhatsApp channel webhook.
    Architecture is in place — plug in Twilio parsing when ready.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Extract Twilio WhatsApp message payload (if present)
    from_number = body.get("From", "").replace("whatsapp:", "")
    message_body = body.get("Body", "").strip()

    if not from_number or not message_body:
        return JSONResponse({"status": "ignored", "reason": "empty payload"})

    # Use WhatsApp number as the session key for persistence
    session_id = f"wa_{from_number}"

    try:
        response_text = handle_message(session_id, message_body)
    except Exception as e:
        log.error(f"WhatsApp handler error: {e}", exc_info=True)
        response_text = (
            "Something went wrong. Please try again or call the branch directly."
        )

    # In production: send `response_text` back via Twilio WhatsApp API
    log.info(f"[WhatsApp] {from_number}: {message_body[:40]} → {response_text[:60]}")

    return JSONResponse({
        "status": "processed",
        "session_id": session_id,
        "response": response_text,
    })


# ─────────────────────────────────────────────────────────────────────────────
# STATIC FILES & ROOT
# ─────────────────────────────────────────────────────────────────────────────

if os.path.exists("web"):
    app.mount("/web", StaticFiles(directory="web"), name="web")


@app.get("/")
async def root():
    index_path = "web/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({
        "service": "Luma Booking Concierge",
        "status": "running",
        "usage": "POST /chat with {message, session_id?, client_id?}",
    })


# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE LOGGING HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _log_turn_to_supabase(
    session_id: str,
    session: dict,
    user_message: str,
    response_text: str,
    latency_ms: int,
    channel: str,
) -> None:
    try:
        supabase.table("sessions").upsert({
            "id": session_id,
            "channel": channel,
            "user_tier": session.get("user_tier", "visitor"),
            "client_id": session.get("client_id"),
            "status": session.get("status", "active"),
            "last_intent": session.get("last_intent"),
            "last_booking_ref": session.get("last_booking_ref"),
            "stage": session.get("stage"),
            "visitor_name": session.get("visitor_name"),
            "visitor_contact": session.get("visitor_contact"),
            "turn": session.get("turn", 0),
        }).execute()

        supabase.table("agent_logs").insert({
            "session_id": session_id,
            "turn": session.get("turn", 1),
            "channel": channel,
            "user_message": user_message,
            "intent": session.get("last_intent"),
            "tool_called": session.get("last_intent"),
            "agent_response": response_text,
            "latency_ms": latency_ms,
            "escalated": session.get("status") == "escalated",
        }).execute()
    except Exception as e:
        log.warning(f"Supabase logging error (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
