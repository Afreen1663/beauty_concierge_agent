"""
consultation.py — Consultation booking helpers for T2 (SPMU) services.

Consultations are free, 30-minute appointments that include a patch test
and design review. They must be completed at least 48 hours before the
main SPMU appointment. Clearance is valid for 6 months.

This module provides:
  - check_consultation_status(): look up whether a client has a valid consultation
  - get_consultation_service_id(): resolve the consultation service ID for a given SPMU service
"""

from datetime import datetime, timedelta, timezone
from api.database import supabase


def check_consultation_status(client_id: str, service_category: str) -> dict:
    """
    Checks whether a client has a valid consultation/patch test clearance
    for a given SPMU service category.

    Returns:
        {
          status: "VALID" | "EXPIRED" | "BOOKED" | "NONE",
          clearance: dict | None,
          message: str | None
        }
    """
    if not client_id:
        return {"status": "NONE", "clearance": None, "message": None}

    try:
        result = (
            supabase.table("spmu_clearances")
            .select("*")
            .eq("client_id", client_id)
            .eq("service_category", service_category)
            .order("cleared_at", desc=True)
            .limit(1)
            .execute()
        )
        clearances = result.data or []
    except Exception as e:
        return {"status": "NONE", "clearance": None, "message": f"Lookup error: {e}"}

    if not clearances:
        return {"status": "NONE", "clearance": None, "message": None}

    clearance = clearances[0]

    try:
        valid_until = datetime.fromisoformat(clearance["valid_until"].replace("Z", "+00:00"))
    except Exception:
        return {"status": "NONE", "clearance": None, "message": "Invalid clearance date."}

    now = datetime.now(timezone.utc)
    if valid_until >= now:
        return {"status": "VALID", "clearance": clearance, "message": None}

    return {
        "status": "EXPIRED",
        "clearance": clearance,
        "message": (
            f"Your patch test clearance expired on "
            f"{valid_until.strftime('%d %B %Y')}. "
            "Clearances are valid for 6 months — you'll need a new consultation."
        ),
    }


def get_consultation_service_id(spmu_service_id: str) -> str | None:
    """
    Returns the service ID for a consultation/patch-test slot.

    Resolution order:
    1. A service with is_consultation=true in the SAME category as the SPMU service
    2. Any service with is_consultation=true (covers a single shared Consultation service)
    3. Any service whose name contains "consultation" (name-based fallback)
    4. Returns None — caller will fall back to spmu_service_id

    Your Supabase has a generic "Consultation" service (category="consultation",
    is_consultation=true) that handles all T2 patch tests, so step 2 will match.
    """
    try:
        # Step 1: same-category consultation service
        svc_result = (
            supabase.table("services")
            .select("id, name, category")
            .eq("id", spmu_service_id)
            .single()
            .execute()
        )
        category = svc_result.data.get("category") if svc_result.data else None

        if category:
            same_cat = (
                supabase.table("services")
                .select("id")
                .eq("category", category)
                .eq("is_consultation", True)
                .limit(1)
                .execute()
            )
            if same_cat.data:
                return same_cat.data[0]["id"]

        # Step 2: any is_consultation=true service (e.g. shared "Consultation" service)
        any_consult = (
            supabase.table("services")
            .select("id")
            .eq("is_consultation", True)
            .limit(1)
            .execute()
        )
        if any_consult.data:
            return any_consult.data[0]["id"]

        # Step 3: name-based fallback
        name_match = (
            supabase.table("services")
            .select("id")
            .ilike("name", "%consultation%")
            .limit(1)
            .execute()
        )
        if name_match.data:
            return name_match.data[0]["id"]

    except Exception as e:
        print(f"[CONSULTATION] get_consultation_service_id error: {e}")

    return None


def format_consultation_confirmation(booking_ref: str, service_name: str,
                                      branch_name: str, slot_datetime: datetime) -> str:
    """Formats a consultation confirmation message."""
    formatted_time = slot_datetime.strftime("%A, %d %B · %I:%M %p")
    return (
        f"Your free consultation is confirmed!\n\n"
        f"Service: {service_name} Consultation\n"
        f"Branch: {branch_name} · {formatted_time}\n"
        f"Reference: {booking_ref}\n\n"
        f"Once your patch test is complete, message us back and "
        f"we'll get you booked in for your {service_name}. "
        f"The earliest appointment is usually 48 hours after your consultation."
    )
