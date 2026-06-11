from datetime import datetime, timezone
from api.database import supabase


def check_service_gate(service_id: str, client_id: str = None) -> dict:
    """
    Checks whether a service can be booked.
    Returns a dict with status and next action.

    Possible statuses:
    - CLEAR: proceed to availability
    - NEEDS_CONSULTATION: T2, no clearance on file
    - CLEARANCE_EXPIRED: T2, clearance older than 6 months
    - NEEDS_SCREENING: T3, no medical clearance on file
    - SCREENING_PENDING: T3, submitted but not yet reviewed
    - HARD_BLOCK: frequency rule violation (injectable too soon)
    """

    # Step 1 — look up the service
    try:
        result = supabase.table("services").select(
            "id, name, service_tier, price_aed, requires_consultation, "
            "requires_screening, min_frequency_weeks, frequency_hard_block, category"
        ).eq("id", service_id).single().execute()
        service = result.data
    except Exception as e:
        return {"status": "ERROR", "message": f"Service not found: {e}"}

    tier = service["service_tier"]

    # Step 2 — T1: no gate, proceed immediately
    if tier == "T1":
        return {
            "status": "CLEAR",
            "tier": "T1",
            "service": service,
            "message": None
        }

    # Step 3 — T2: check SPMU clearance
    if tier == "T2":
        if not client_id:
            # Visitor: always needs consultation
            return {
                "status": "NEEDS_CONSULTATION",
                "tier": "T2",
                "service": service,
                "message": (
                    f"{service['name']} is a semi-permanent treatment. "
                    "To make sure it's right for your skin, we start with a free "
                    "consultation and patch test. The patch test needs to be done "
                    "at least 48 hours before your main appointment. "
                    "Would you like to book a free consultation first? "
                    "It takes about 30 minutes and includes a patch test and design review."
                )
            }

        # Client: check clearance record
        try:
            result = supabase.table("spmu_clearances").select("*") \
                .eq("client_id", client_id) \
                .eq("service_category", service["category"]) \
                .order("cleared_at", desc=True) \
                .limit(1) \
                .execute()
            clearances = result.data
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
                )
            }

        clearance = clearances[0]
        valid_until = datetime.fromisoformat(clearance["valid_until"].replace("Z", "+00:00"))

        if valid_until < datetime.now(timezone.utc):
            return {
                "status": "CLEARANCE_EXPIRED",
                "tier": "T2",
                "service": service,
                "message": (
                    f"Your patch test clearance for {service['name']} has expired — "
                    "it's valid for 6 months. You'll need a new consultation before "
                    "we can book you in. Would you like to schedule one?"
                )
            }

        # Clearance valid — proceed
        return {"status": "CLEAR", "tier": "T2", "service": service, "message": None}

    # Step 4 — T3: check medical screening
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
                )
            }

        # Client: check medical screening
        try:
            result = supabase.table("medical_screenings").select("*") \
                .eq("client_id", client_id) \
                .eq("service_category", service["category"]) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            screenings = result.data
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
                )
            }

        screening = screenings[0]
        status = screening["status"]

        if status == "PENDING":
            return {
                "status": "SCREENING_PENDING",
                "tier": "T3",
                "service": service,
                "message": (
                    "Your medical screening is currently under review. "
                    "Our team usually responds within 24 hours. "
                    f"Your reference is: {screening['id']}."
                )
            }

        if status == "APPROVED":
            approved_until = datetime.fromisoformat(
                screening["approved_until"].replace("Z", "+00:00")
            )
            if approved_until >= datetime.now(timezone.utc):
                return {
                    "status": "CLEAR",
                    "tier": "T3",
                    "service": service,
                    "message": None
                }
            else:
                return {
                    "status": "NEEDS_SCREENING",
                    "tier": "T3",
                    "service": service,
                    "message": (
                        "Your medical clearance has expired (valid for 90 days). "
                        "We'll need to run through the screening questions again. Ready?"
                    )
                }

        if status == "FLAGGED":
            return {
                "status": "NEEDS_SCREENING",
                "tier": "T3",
                "service": service,
                "message": (
                    "Based on your previous screening, our team needs to speak "
                    "with you before booking. Please call the branch directly "
                    "or would you like me to escalate to our team now?"
                )
            }

    return {"status": "ERROR", "message": "Unknown service tier"}