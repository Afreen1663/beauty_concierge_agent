"""
bookings.py — Booking creation, slot locking, and payment handling.

Core booking engine implementing the following spec rules:
  - Slot locking: UPDATE time_slots WHERE status='available' (race-condition safe)
  - Payment rules: consultation=free, package=100% upfront, <=AED1000=full, >AED1000=20% deposit
  - Confirmation formats: full upfront, deposit, consultation
  - Stripe test mode payment links (falls back to mock URL)
  - Atomic rollback: if booking INSERT fails, slot is released
"""

import os
import random
import string
import stripe
from datetime import datetime, timezone
from api.database import supabase

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


# ─────────────────────────────────────────────────────────────────────────────
# PAYMENT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def generate_booking_ref(prefix: str = "BKG") -> str:
    """Generates a unique booking reference like BKG-2026-A3X9."""
    year = datetime.now().year
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{year}-{suffix}"


def calculate_payment(price_aed: float, booking_type: str = "single") -> dict:
    """
    Applies the spec payment rules:
      - consultation → free
      - package      → 100% upfront
      - single ≤ AED 1,000 → 100% upfront
      - single > AED 1,000 → 20% deposit
    """
    if booking_type == "consultation":
        return {
            "payment_type": "free",
            "deposit_amount_aed": 0.0,
            "balance_due_aed": 0.0,
            "payment_required": False,
        }

    if booking_type == "package":
        return {
            "payment_type": "full_upfront",
            "deposit_amount_aed": price_aed,
            "balance_due_aed": 0.0,
            "payment_required": True,
        }

    # Single service
    if price_aed <= 1000:
        return {
            "payment_type": "full_upfront",
            "deposit_amount_aed": price_aed,
            "balance_due_aed": 0.0,
            "payment_required": True,
        }
    else:
        deposit = round(price_aed * 0.20)
        return {
            "payment_type": "deposit_20pct",
            "deposit_amount_aed": float(deposit),
            "balance_due_aed": price_aed - deposit,
            "payment_required": True,
        }


def generate_payment_link(booking_ref: str, amount_aed: float) -> str:
    """
    Creates a Stripe Checkout Session in test mode.
    Falls back to a mock URL if Stripe is not configured.
    """
    sk = os.getenv("STRIPE_SECRET_KEY", "")
    if sk.startswith("sk_"):
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "aed",
                        "product_data": {"name": f"Booking {booking_ref}"},
                        "unit_amount": int(amount_aed * 100),
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=os.getenv("STRIPE_SUCCESS_URL", "https://example.com/success"),
                cancel_url=os.getenv("STRIPE_CANCEL_URL", "https://example.com/cancel"),
                metadata={"booking_ref": booking_ref},
            )
            return session.url
        except Exception as e:
            print(f"[STRIPE] Error generating link: {e}")

    # Mock URL fallback
    return f"https://pay.stripe.com/test/{booking_ref}?amount={int(amount_aed * 100)}"


# ─────────────────────────────────────────────────────────────────────────────
# SLOT LOCKING
# ─────────────────────────────────────────────────────────────────────────────

def lock_slot(slot_id: str) -> bool:
    """
    Atomically claims a slot: UPDATE WHERE status='available'.
    Returns True if locked successfully, False if already taken.
    """
    try:
        result = (
            supabase.table("time_slots")
            .update({"status": "booked"})
            .eq("id", slot_id)
            .eq("status", "available")
            .execute()
        )
        return len(result.data) > 0
    except Exception as e:
        print(f"[SLOT LOCK] Error: {e}")
        return False


def release_slot(slot_id: str) -> None:
    """Releases a slot back to 'available' — called when booking INSERT fails."""
    try:
        supabase.table("time_slots").update(
            {"status": "available"}
        ).eq("id", slot_id).execute()
    except Exception as e:
        print(f"[SLOT RELEASE] Error releasing slot {slot_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# BOOKING CREATION
# ─────────────────────────────────────────────────────────────────────────────

def create_booking(
    service_id: str,
    slot_id: str,
    branch_id: str,
    client_id: str = None,
    visitor_name: str = None,
    visitor_contact: str = None,
    notes: str = None,
    booking_type: str = "single",
    artist_id: str = None,
    screening_ref: str = None,
    clearance_ref: str = None,
) -> dict:
    """
    Creates a confirmed booking in Supabase.

    Flow:
    1. Look up service and slot
    2. Pre-check slot availability
    3. Lock slot (race-safe UPDATE WHERE status='available')
    4. Calculate payment
    5. Generate booking ref + payment link
    6. INSERT booking record (release slot if this fails)
    7. Return confirmation dict

    Returns:
        {
          status:      "SUCCESS" | "SLOT_TAKEN" | "ERROR"
          booking_ref: str
          payment:     dict
          payment_link: str | None
          message:     str  (full confirmation text)
        }
    """

    # ── 1. Look up service ────────────────────────────────────────────────────
    try:
        svc_result = (
            supabase.table("services")
            .select("id, name, price_aed, service_tier, category")
            .eq("id", service_id)
            .single()
            .execute()
        )
        service = svc_result.data
    except Exception as e:
        return {"status": "ERROR", "message": f"Service lookup failed: {e}"}

    # ── 2. Look up slot ───────────────────────────────────────────────────────
    try:
        slot_result = (
            supabase.table("time_slots")
            .select("id, start_time, end_time, artist_id, status, branches(name)")
            .eq("id", slot_id)
            .single()
            .execute()
        )
        slot = slot_result.data
    except Exception as e:
        return {"status": "ERROR", "message": f"Slot lookup failed: {e}"}

    if slot.get("status") != "available":
        return {
            "status": "SLOT_TAKEN",
            "message": (
                "Sorry, that slot was just taken by someone else. "
                "Let me show you the next available options."
            ),
        }

    # ── 3. Lock slot ──────────────────────────────────────────────────────────
    if not lock_slot(slot_id):
        return {
            "status": "SLOT_TAKEN",
            "message": (
                "Sorry, that slot was just booked by someone else. "
                "Let me show you the next available options."
            ),
        }

    # ── 4. Calculate payment ──────────────────────────────────────────────────
    payment = calculate_payment(service["price_aed"], booking_type)

    # ── 5. Generate refs and payment link ─────────────────────────────────────
    prefix = "CON" if booking_type == "consultation" else "BKG"
    booking_ref = generate_booking_ref(prefix)

    payment_link = None
    if payment["payment_required"]:
        payment_link = generate_payment_link(booking_ref, payment["deposit_amount_aed"])

    # ── 6. Build and insert booking record ───────────────────────────────────
    consent_status = "pending" if service.get("service_tier") == "T3" else "not_required"

    booking_record = {
        "id": booking_ref,
        "service_id": service_id,
        "slot_id": slot_id,
        "branch_id": branch_id,
        "status": "confirmed",
        "booking_type": booking_type,
        "payment_type": payment["payment_type"],
        "deposit_amount_aed": payment["deposit_amount_aed"],
        "balance_due_aed": payment["balance_due_aed"],
        "payment_status": "payment_initiated" if payment["payment_required"] else "not_required",
        "payment_link": payment_link,
        "notes": notes,
        "screening_ref": screening_ref,
        "clearance_ref": clearance_ref,
        "consent_status": consent_status,
        "channel": "web",
        "booking_source": "ai_concierge",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if client_id:
        booking_record["client_id"] = client_id
        booking_record["artist_id"] = artist_id or slot.get("artist_id")
    else:
        booking_record["visitor_name"] = visitor_name or ""
        booking_record["visitor_contact"] = visitor_contact or ""

    try:
        supabase.table("bookings").insert(booking_record).execute()
    except Exception as e:
        release_slot(slot_id)
        return {"status": "ERROR", "message": f"Booking creation failed: {e}"}

    # ── 7. Format confirmation message ────────────────────────────────────────
    try:
        start_dt = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
        formatted_time = start_dt.strftime("%A, %d %B · %I:%M %p")
    except Exception:
        formatted_time = slot.get("start_time", "")[:16]

    branch_name = (
        slot.get("branches", {}).get("name", "our branch")
        if isinstance(slot.get("branches"), dict)
        else "our branch"
    )

    message = _format_confirmation(
        booking_type=booking_type,
        service=service,
        branch_name=branch_name,
        formatted_time=formatted_time,
        booking_ref=booking_ref,
        payment=payment,
        payment_link=payment_link,
        consent_status=consent_status,
    )

    return {
        "status": "SUCCESS",
        "booking_ref": booking_ref,
        "payment": payment,
        "payment_link": payment_link,
        "message": message,
    }


def _format_confirmation(
    booking_type: str,
    service: dict,
    branch_name: str,
    formatted_time: str,
    booking_ref: str,
    payment: dict,
    payment_link: str | None,
    consent_status: str,
) -> str:
    """Builds the human-readable booking confirmation message."""

    if booking_type == "consultation":
        msg = (
            f"Your free consultation is confirmed!\n\n"
            f"Service: {service['name']} Consultation\n"
            f"Branch: {branch_name} · {formatted_time}\n"
            f"Reference: {booking_ref}\n\n"
            f"Once your patch test is complete, message us back and "
            f"we'll get you booked in for your {service['name']}. "
            f"The earliest appointment is usually 48 hours after your consultation."
        )

    elif payment["payment_type"] == "full_upfront":
        msg = (
            f"Booking confirmed!\n\n"
            f"Service: {service['name']}\n"
            f"Branch: {branch_name} · {formatted_time}\n"
            f"Total: AED {service['price_aed']:.0f}\n\n"
            f"Payment is required to secure your slot.\n"
            f"Pay: {payment_link}\n"
            f"(Link valid for 24 hours)\n\n"
            f"Reference: {booking_ref}"
        )

    else:  # deposit_20pct
        msg = (
            f"Booking confirmed!\n\n"
            f"Service: {service['name']} — AED {service['price_aed']:.0f}\n"
            f"Branch: {branch_name} · {formatted_time}\n\n"
            f"A 20% deposit of AED {payment['deposit_amount_aed']:.0f} is required to secure your slot.\n"
            f"The remaining AED {payment['balance_due_aed']:.0f} is payable at the branch.\n"
            f"Pay deposit: {payment_link}\n"
            f"(Link valid for 24 hours)\n\n"
            f"Reference: {booking_ref}"
        )

    if consent_status == "pending":
        msg += "\n\nA digital consent form will be sent to you 48 hours before your appointment."

    return msg
