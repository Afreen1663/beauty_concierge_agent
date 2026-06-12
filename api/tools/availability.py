"""
availability.py — Slot availability queries against Supabase.
All date handling uses Dubai local time (UTC+4), converted to UTC for DB queries.
"""

from datetime import datetime, timedelta, timezone
from api.database import supabase

# Dubai is UTC+4
DUBAI_TZ = timezone(timedelta(hours=4))

_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}


def _parse_date(date_str: str) -> datetime | None:
    """
    Resolves a natural-language or explicit date string.
    Returns a timezone-aware datetime in Dubai time (UTC+4).
    Handles: today, tomorrow, day names, "this/next X", ordinals like "6th July".
    """
    today = datetime.now(DUBAI_TZ)
    lower = date_str.lower().strip()

    # Strip common prefixes: "this saturday", "next friday", "on monday"
    for prefix in ("this ", "next ", "on ", "for "):
        if lower.startswith(prefix):
            lower = lower[len(prefix):]
            break

    # Remove ordinal suffixes: "6th" -> "6", "21st" -> "21"
    lower = __import__("re").sub(r"(\d+)(st|nd|rd|th)\b", r"\1", lower)

    if lower == "today":
        return today.replace(hour=0, minute=0, second=0, microsecond=0)
    if lower == "tomorrow":
        return (today + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Day name matching
    for day_name, weekday in _WEEKDAY_MAP.items():
        if lower == day_name or lower.startswith(day_name):
            days_ahead = (weekday - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target = today + timedelta(days=days_ahead)
            return target.replace(hour=0, minute=0, second=0, microsecond=0)

    # Try explicit formats — also try stripped version without ordinals
    for fmt in (
        "%d %B",    # "6 July"
        "%B %d",    # "July 6"
        "%d %b",    # "6 Jul"
        "%b %d",    # "Jul 6"
        "%d/%m",    # "06/07"
        "%Y-%m-%d", # "2026-07-06"
        "%d-%m-%Y", # "06-07-2026"
    ):
        for candidate in (lower.strip(), date_str.strip()):
            try:
                parsed = datetime.strptime(candidate, fmt)
                # Assign current year if not in format
                if parsed.year == 1900:
                    parsed = parsed.replace(year=today.year)
                # If the date has already passed this year, assume next year
                parsed = parsed.replace(tzinfo=DUBAI_TZ, hour=0, minute=0, second=0, microsecond=0)
                if parsed.date() < today.date():
                    parsed = parsed.replace(year=today.year + 1)
                return parsed
            except ValueError:
                continue

    return None


def check_availability(
    service_id: str,
    branch_id: str = None,
    date_str: str = None,
    artist_id: str = None,
    limit: int = 5,
) -> dict:
    try:
        query = (
            supabase.table("time_slots")
            .select("id, start_time, end_time, branch_id, artist_id, branches(id, name), artists(name)")
            .eq("service_id", service_id)
            .eq("status", "available")
        )

        if branch_id:
            query = query.eq("branch_id", branch_id)
        if artist_id:
            query = query.eq("artist_id", artist_id)

        requested_date_label = date_str or "that date"

        if date_str:
            target = _parse_date(date_str)
            if target:
                # Build day window in Dubai time, then convert to UTC for Supabase
                day_start_dubai = target.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end_dubai   = target.replace(hour=23, minute=59, second=59, microsecond=0)

                day_start_utc = day_start_dubai.astimezone(timezone.utc)
                day_end_utc   = day_end_dubai.astimezone(timezone.utc)

                query = (
                    query
                    .gte("start_time", day_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
                    .lte("start_time", day_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
                )
            else:
                # date_str was provided but couldn't be parsed — fall through to future slots
                print(f"[AVAILABILITY] Could not parse date_str: '{date_str}'")
                now_dubai = datetime.now(DUBAI_TZ)
                query = query.gte("start_time", now_dubai.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        else:
            now_dubai = datetime.now(DUBAI_TZ)
            query = query.gte("start_time", now_dubai.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

        result = query.order("start_time").limit(limit).execute()
        slots = result.data or []

        if not slots:
            # Fallback — next 5 available slots on any future date
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fallback_query = (
                supabase.table("time_slots")
                .select("id, start_time, end_time, branch_id, artist_id, branches(id, name), artists(name)")
                .eq("service_id", service_id)
                .eq("status", "available")
                .gte("start_time", now_utc)
                .order("start_time")
                .limit(5)
            )
            if branch_id:
                fallback_query = fallback_query.eq("branch_id", branch_id)

            fallback_result = fallback_query.execute()
            alternatives = fallback_result.data or []

            return {
                "status": "NO_AVAILABILITY",
                "slots": [],
                "alternatives": alternatives,
                "message": (
                    f"No slots available on {requested_date_label}."
                    + (" Here are the next available times:" if alternatives else " No upcoming slots found.")
                ),
            }

        return {
            "status": "AVAILABLE",
            "slots": slots,
            "alternatives": [],
            "message": f"Found {len(slots)} available slot(s).",
        }

    except Exception as e:
        print(f"[AVAILABILITY] check_availability error: {e}")
        return {
            "status": "ERROR",
            "message": str(e),
            "slots": [],
            "alternatives": [],
        }


def resolve_service_id(service_name: str) -> str | None:
    """
    Resolves a service ID from a string.

    Handles two cases:
    1. service_name is a short, clean service name (e.g. "Brow SPMU")
       -> direct ilike match
    2. service_name is a full sentence (e.g. "I want to book Brow SPMU")
       -> fetch all services and check if any service name appears
          as a substring within the message (longest match wins)
    """
    text = service_name.strip()
    if not text:
        return None

    try:
        # First try: direct ilike match (works for clean short strings)
        result = (
            supabase.table("services")
            .select("id, name")
            .ilike("name", f"%{text}%")
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["id"]

        # Second try: reverse match — does any service name appear
        # inside the user's message? Pick the longest matching name
        # to avoid short names (e.g. "Lip") matching too eagerly.
        all_services = (
            supabase.table("services")
            .select("id, name")
            .execute()
        )
        lower_text = text.lower()
        best_match = None
        best_len = 0

        for svc in (all_services.data or []):
            svc_name_lower = svc["name"].lower()
            if svc_name_lower in lower_text:
                if len(svc_name_lower) > best_len:
                    best_match = svc
                    best_len = len(svc_name_lower)

        if best_match:
            return best_match["id"]

    except Exception as e:
        print(f"[AVAILABILITY] resolve_service_id error: {e}")

    return None


def resolve_branch_id(branch_name: str) -> str | None:
    try:
        result = (
            supabase.table("branches")
            .select("id, name")
            .ilike("name", f"%{branch_name}%")
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["id"]
    except Exception as e:
        print(f"[AVAILABILITY] resolve_branch_id error: {e}")
    return None


def resolve_artist_id(artist_name: str) -> str | None:
    try:
        result = (
            supabase.table("artists")
            .select("id, name")
            .ilike("name", f"%{artist_name}%")
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["id"]
    except Exception as e:
        print(f"[AVAILABILITY] resolve_artist_id error: {e}")
    return None