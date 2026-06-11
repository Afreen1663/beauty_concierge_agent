from datetime import datetime, timezone
from api.database import supabase

SCREENING_QUESTIONS = [
    {
        "id": "q1_pregnant",
        "question": "Are you pregnant or breastfeeding?",
        "flag_if": True
    },
    {
        "id": "q2_blood_thinners",
        "question": "Are you currently taking blood thinners or anticoagulants?",
        "flag_if": True
    },
    {
        "id": "q3_allergies",
        "question": "Do you have any known allergies to anaesthetics, lidocaine, or hyaluronic acid?",
        "flag_if": True
    },
    {
        "id": "q4_prior_procedures",
        "question": "Have you had any facial surgery or aesthetic procedures in the last 6 months?",
        "flag_if": True
    },
    {
        "id": "q5_active_infection",
        "question": "Do you have any active skin infections, cold sores, or open wounds on the treatment area?",
        "flag_if": True
    },
    {
        "id": "q6_autoimmune",
        "question": "Do you have any autoimmune conditions or are you on immunosuppressant medication?",
        "flag_if": True
    },
]


def get_next_question(answers_so_far: dict) -> dict | None:
    """
    Returns the next unanswered screening question, or None if all done.
    """
    for q in SCREENING_QUESTIONS:
        if q["id"] not in answers_so_far:
            return q
    return None


def parse_yes_no(text: str) -> bool | None:
    """
    Parses a user's yes/no answer into a boolean.
    Returns None if unclear.
    """
    text = text.lower().strip()
    
    # Check no first — more specific patterns take priority
    no_patterns = ["no", "nope", "nah", "don't", "dont", "haven't", "havent", "not really", "i do not", "i don't"]
    for pattern in no_patterns:
        if pattern in text:
            return False
    
    # Then check yes
    yes_patterns = ["yes", "yeah", "yep", "yup", "i am", "i do", "i have", "correct", "absolutely"]
    for pattern in yes_patterns:
        if pattern in text:
            return True
    
    return None


def submit_screening(
    service_id: str,
    service_category: str,
    answers: dict,
    client_id: str = None,
    visitor_name: str = None,
    visitor_contact: str = None,
) -> dict:
    """
    Submits a completed screening form to Supabase.
    Checks for flagged answers and sets status accordingly.
    """

    # Check which questions were flagged
    flagged = []
    for q in SCREENING_QUESTIONS:
        if answers.get(q["id"]) == True and q["flag_if"] == True:
            flagged.append(q["id"])

    # Generate screening ref
    year = datetime.now().year
    import random, string
    suffix = ''.join(random.choices(string.digits, k=4))
    screening_ref = f"SCR-{year}-{suffix}"

    record = {
        "id": screening_ref,
        "service_category": service_category,
        "answers": answers,
        "flagged_questions": flagged,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if client_id:
        record["client_id"] = client_id
    else:
        record["visitor_name"] = visitor_name
        record["visitor_contact"] = visitor_contact

    try:
        supabase.table("medical_screenings").insert(record).execute()
    except Exception as e:
        return {"status": "ERROR", "message": f"Screening submission failed: {e}"}

    if flagged:
        return {
            "status": "FLAGGED",
            "screening_ref": screening_ref,
            "flagged_questions": flagged,
            "message": (
                "Thank you for completing the screening. Based on your answers, "
                "our medical team needs to review your case before we can proceed. "
                "Someone will be in touch within 24 hours. "
                f"Your reference is: {screening_ref}."
            )
        }

    return {
        "status": "SUBMITTED",
        "screening_ref": screening_ref,
        "message": (
            "Your screening has been submitted. Our team will review it "
            f"and get back to you within 24 hours. Reference: {screening_ref}."
        )
    }