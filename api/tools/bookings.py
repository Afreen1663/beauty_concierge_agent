import random
import string
from datetime import datetime, timezone
from api.database import supabase


def generate_booking_ref(prefix: str = "BKG") -> str:
    """Generates a unique booking reference like BKG-2026-A3X9"""
    year = datetime.now().year
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{year}-{suffix}"


def calculate_payment(price_aed: float, booking_type: str = "single") -> dict:
    """
    Applies payment rules from the spec:
    - Single ≤ AED 1,000: full upfront
    - Single > AED 1,000: 20% deposit
    - Package: full upfront
    - Consultation: free
    """
    if booking_type == "consultation":
        return {
            "payment_type": "free",
            "deposit_amount_aed": 0,
            "balance_due_aed": 0,
            "payment_required": False
        }

    if booking_type == "package":
        return {
            "payment_type": "full_upfront",
            "deposit_amount_aed": price_aed,
            "balance_due_aed": 0,
            "payment_required": True
        }

    # Single service
    if price_aed <= 1000:
        return {
            "payment_type": "full_upfront",
            "deposit_amount_aed": price_aed,
            "balance_due_aed": 0,
            "payment_required": True
        }
    else:
        deposit = round(price_aed * 0.20)
        return {
            "payment_type": "deposit_20pct",
            "deposit_amount_aed": deposit,
            "balance_due_aed": price_aed - deposit,
            "payment_required": True
        }


def generate_payment_link(booking_ref: str, amount_aed: float) -> str:
    """Stub: returns a mock Stripe payment link"""
    return f"https://pay.stripe.com/test/{booking_ref}?amount={int(amount_aed * 100)}"


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
    Returns booking reference, payment info, and confirmation message.
    """

    # Look up service for price
    try:
        svc_result = supabase.table("services").select(
            "id, name, price_aed, service_tier"
        ).eq("id", service_id).single().execute()
        service = svc_result.data
    except Exception as e:
        return {"status": "ERROR", "message": f"Service lookup failed: {e}"}

    # Look up slot for time info
    try:
        slot_result = supabase.table("time_slots").select(
            "id, start_time, end_time, artist_id, branches(name)"
        ).eq("id", slot_id).single().execute()
        slot = slot_result.data
    except Exception as e:
        return {"status": "ERROR", "message": f"Slot lookup failed: {e}"}

    # Calculate payment
    payment = calculate_payment(service["price_aed"], booking_type)

    # Generate booking ref
    prefix = "CON" if booking_type == "consultation" else "BKG"
    booking_ref = generate_booking_ref(prefix)

    # Generate payment link if needed
    payment_link = None
    if payment["payment_required"]:
        payment_link = generate_payment_link(booking_ref, payment["deposit_amount_aed"])

    # Determine consent status for T3
    consent_status = "not_required"
    if service["service_tier"] == "T3":
        consent_status = "pending"

    # Build booking record
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
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if client_id:
        booking_record["client_id"] = client_id
        booking_record["artist_id"] = artist_id or slot.get("artist_id")
    else:
        booking_record["visitor_name"] = visitor_name
        booking_record["visitor_contact"] = visitor_contact

    # Insert into Supabase
    try:
        supabase.table("time_slots").update(
            {"status": "booked"}
        ).eq("id", slot_id).execute()

        supabase.table("bookings").insert(booking_record).execute()
    except Exception as e:
        return {"status": "ERROR", "message": f"Booking creation failed: {e}"}

    # Format start time for display
    start_dt = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
    formatted_time = start_dt.strftime("%A, %d %B · %I:%M %p")
    branch_name = slot.get("branches", {}).get("name", "our branch")

    # Build confirmation message
    if booking_type == "consultation":
        message = (
            f"Your free consultation is confirmed!\n\n"
            f"Service: {service['name']} Consultation\n"
            f"Branch: {branch_name} · {formatted_time}\n"
            f"Reference: {booking_ref}\n\n"
            f"Once your patch test is complete, message us back and "
            f"we'll get you booked in for your {service['name']} — "
            f"usually the earliest is 48 hours after your consultation."
        )
    elif payment["payment_type"] == "full_upfront":
        message = (
            f"Here's your booking summary:\n\n"
            f"Service: {service['name']}\n"
            f"Branch: {branch_name} · {formatted_time}\n"
            f"Total: AED {service['price_aed']:.0f}\n\n"
            f"Payment is required to confirm your slot.\n"
            f"💳 Pay: {payment_link}\n"
            f"(Link valid for 24 hours)\n\n"
            f"Booking reference: {booking_ref}"
        )
    else:
        message = (
            f"Here's your booking summary:\n\n"
            f"Service: {service['name']} — AED {service['price_aed']:.0f}\n"
            f"Branch: {branch_name} · {formatted_time}\n\n"
            f"A 20% deposit of AED {payment['deposit_amount_aed']:.0f} is required "
            f"to secure your booking. The remaining AED {payment['balance_due_aed']:.0f} "
            f"is payable at the branch on the day.\n"
            f"💳 Pay deposit: {payment_link}\n"
            f"(Link valid for 24 hours)\n\n"
            f"Booking reference: {booking_ref}"
        )

    if consent_status == "pending":
        message += "\n\nA digital consent form will be sent to you 48 hours before your appointment."

    return {
        "status": "SUCCESS",
        "booking_ref": booking_ref,
        "payment": payment,
        "payment_link": payment_link,
        "message": message
    }