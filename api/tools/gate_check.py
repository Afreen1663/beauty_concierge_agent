"""
gate_check.py — Pre-booking gate enforcement for service tiers T1, T2, T3.

T1 — Standard beauty: no gate, proceed to availability immediately.
T2 — SPMU: requires consultation + patch test clearance (valid 6 months).
T3 — Medical/injectable: requires medical screening + clearance (valid 90 days).

All gate checks run against Supabase. Clients (with client_id) have their
records looked up; visitors always trigger the consultation/screening flow.
"""

from datetime import datetime, timezone
from api.database import supabase


def check_service_gate(service_id: str, client_id: str = None) -> dict:
    """
    Evaluates whether a service can be booked immediately.

    Returns a dict with:
        status  : "CLEAR" | "NEEDS_CONSULTATION" | "CLEARANCE_EXPIRED" |
                  "NEEDS_SCREENING" | "SCREENING_PENDING" | "HARD_BLOCK" | "ERROR"
        tier    : "T1" | "T2" | "T3"
        service : full service record dict
        message : conversational explanation (None if CLEAR)
    """

    # ── Step 1: Look up service ───────────────────────────────────────────────
    try:
        result = (
            supabase.table("services")
            .select(
                "id, name, service_tier, price_aed, requires_consultation, "
                "requires_screening, min_frequency_weeks, frequency_hard_block, category"
            )
            .eq("id", service_id)
            .single()
            .execute()
        )
        service = result.data
    except Exception as e:
        return {"status": "ERROR", "message": f"Service lookup failed: {e}"}

    tier = service.get("service_tier", "T1")

    # ── T1: No gate ───────────────────────────────────────────────────────────
    if tier == "T1":
        return {"status": "CLEAR", "tier": "T1", "service": service, "message": None}

    # ── T2: SPMU — consultation + patch test ──────────────────────────────────
    if tier == "T2":
        if not client_id:
            return {
                "status": "NEEDS_CONSULTATION",
                "tier": "T2",
                "service": service,
                "message": (
                    f"{service['name']} is a semi-permanent treatment. "
                    "To make sure it's right for your skin, we start with a free "
                    "consultation and patch test. The patch test needs to be done "
                    "at least 48 hours before your main appointment. "
                    "Would you like to book a free consultation? "
                    "It takes about 30 minutes and includes a patch test and design review."
                ),
            }

        try:
            result = (
                supabase.table("spmu_clearances")
                .select("*")
                .eq("client_id", client_id)
                .eq("service_category", service["category"])
                .order("cleared_at", desc=True)
                .limit(1)
                .execute()
            )
            clearances = result.data or []
        except Exception as e:
            return {"status": "ERROR", "message": f"Clearance lookup failed: {e}"}

        if not clearances:
            return {
                "status": "NEEDS_CONSULTATION",
                "tier": "T2",
                "service": service,
                "message": (
                    f"{service['name']} requires a free consultation and patch test first. "
                    "Would you like to book a free consultation? "
                    "It takes about 30 minutes and includes a patch test and design review."
                ),
            }

        clearance = clearances[0]
        try:
            valid_until = datetime.fromisoformat(clearance["valid_until"].replace("Z", "+00:00"))
        except Exception:
            return {"status": "ERROR", "message": "Invalid clearance date format."}

        if valid_until < datetime.now(timezone.utc):
            return {
                "status": "CLEARANCE_EXPIRED",
                "tier": "T2",
                "service": service,
                "message": (
                    f"Your patch test clearance for {service['name']} has expired — "
                    "it's valid for 6 months. You'll need a new consultation before "
                    "we can book you in. Would you like to schedule one?"
                ),
            }

        return {"status": "CLEAR", "tier": "T2", "service": service, "message": None}

    # ── T3: Medical / Injectable ──────────────────────────────────────────────
    if tier == "T3":
        if not client_id:
            return {
                "status": "NEEDS_SCREENING",
                "tier": "T3",
                "service": service,
                "message": (
                    f"{service['name']} is a medical treatment performed by our qualified "
                    "practitioners. Before I can book you in, we need to complete a short "
                    "health screening — just 6 quick questions. Our medical team reviews "
                    "your answers and usually responds within 24 hours. Ready to start?"
                ),
            }

        try:
            result = (
                supabase.table("medical_screenings")
                .select("*")
                .eq("client_id", client_id)
                .eq("service_category", service["category"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            screenings = result.data or []
        except Exception as e:
            return {"status": "ERROR", "message": f"Screening lookup failed: {e}"}

        if not screenings:
            return {
                "status": "NEEDS_SCREENING",
                "tier": "T3",
                "service": service,
                "message": (
                    f"{service['name']} is a medical treatment. "
                    "Before I can book you in, we need to complete a short health "
                    "screening — just 6 quick questions. Ready to start?"
                ),
            }

        screening = screenings[0]
        status = screening.get("status", "PENDING")

        if status == "PENDING":
            return {
                "status": "SCREENING_PENDING",
                "tier": "T3",
                "service": service,
                "message": (
                    "Your medical screening is currently under review. "
                    "Our team usually responds within 24 hours. "
                    f"Your reference is: {screening['id']}."
                ),
            }

        if status == "APPROVED":
            try:
                approved_until = datetime.fromisoformat(
                    screening["approved_until"].replace("Z", "+00:00")
                )
            except Exception:
                return {"status": "ERROR", "message": "Invalid approved_until date format."}

            if approved_until >= datetime.now(timezone.utc):
                return {"status": "CLEAR", "tier": "T3", "service": service, "message": None}
            else:
                return {
                    "status": "NEEDS_SCREENING",
                    "tier": "T3",
                    "service": service,
                    "message": (
                        "Your medical clearance has expired (valid for 90 days). "
                        "We'll need to run through the screening questions again. Ready?"
                    ),
                }

        if status == "FLAGGED":
            return {
                "status": "NEEDS_SCREENING",
                "tier": "T3",
                "service": service,
                "message": (
                    "Based on your previous screening, our medical team needs to speak "
                    "with you before we can proceed. Would you like me to connect you "
                    "with our team now?"
                ),
            }

        if status == "REJECTED":
            return {
                "status": "HARD_BLOCK",
                "tier": "T3",
                "service": service,
                "message": (
                    "Unfortunately, based on your medical screening, our practitioners "
                    "are unable to perform this treatment at this time. "
                    "Please call the branch directly if you'd like to discuss further."
                ),
            }

    return {"status": "ERROR", "message": f"Unknown service tier: {tier}"}
