from datetime import datetime, timedelta, timezone
from api.database import supabase


def check_availability(service_id: str, branch_id: str = None, date_str: str = None) -> dict:
    """
    Queries available slots for a service, optionally filtered by branch and date.
    Returns up to 5 available slots.
    """

    try:
        query = supabase.table("time_slots").select(
            "id, start_time, end_time, branch_id, artist_id, "
            "branches(name), artists(name)"
        ).eq("service_id", service_id).eq("status", "available")

        if branch_id:
            query = query.eq("branch_id", branch_id)

        # Date filtering
        if date_str:
            # Parse relative dates
            today = datetime.now(timezone.utc)
            date_lower = date_str.lower().strip()

            if date_lower == "tomorrow":
                target = today + timedelta(days=1)
            elif date_lower == "today":
                target = today
            elif date_lower in ["saturday", "saturday"]:
                days_ahead = (5 - today.weekday()) % 7
                target = today + timedelta(days=days_ahead if days_ahead > 0 else 7)
            elif date_lower == "sunday":
                days_ahead = (6 - today.weekday()) % 7
                target = today + timedelta(days=days_ahead if days_ahead > 0 else 7)
            elif date_lower == "monday":
                days_ahead = (0 - today.weekday()) % 7
                target = today + timedelta(days=days_ahead if days_ahead > 0 else 7)
            elif date_lower == "tuesday":
                days_ahead = (1 - today.weekday()) % 7
                target = today + timedelta(days=days_ahead if days_ahead > 0 else 7)
            elif date_lower == "wednesday":
                days_ahead = (2 - today.weekday()) % 7
                target = today + timedelta(days=days_ahead if days_ahead > 0 else 7)
            elif date_lower == "thursday":
                days_ahead = (3 - today.weekday()) % 7
                target = today + timedelta(days=days_ahead if days_ahead > 0 else 7)
            elif date_lower == "friday":
                days_ahead = (4 - today.weekday()) % 7
                target = today + timedelta(days=days_ahead if days_ahead > 0 else 7)
            else:
                # Try parsing as a real date e.g. "5 July", "July 5"
                try:
                    target = datetime.strptime(date_str, "%d %B").replace(
                        year=datetime.now().year, tzinfo=timezone.utc
                    )
                except ValueError:
                    try:
                        target = datetime.strptime(date_str, "%B %d").replace(
                            year=datetime.now().year, tzinfo=timezone.utc
                        )
                    except ValueError:
                        target = None

            if target:
                day_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = target.replace(hour=23, minute=59, second=59, microsecond=0)
                query = query.gte("start_time", day_start.isoformat())
                query = query.lte("start_time", day_end.isoformat())

        result = query.order("start_time").limit(5).execute()
        slots = result.data

        if not slots:
            # Try fetching next 3 available slots on any date as alternatives
            fallback = supabase.table("time_slots").select(
                "id, start_time, end_time, branch_id, artist_id, "
                "branches(name), artists(name)"
            ).eq("service_id", service_id).eq("status", "available") \
             .gte("start_time", datetime.now(timezone.utc).isoformat()) \
             .order("start_time").limit(3).execute()

            return {
                "status": "NO_AVAILABILITY",
                "slots": [],
                "alternatives": fallback.data,
                "message": "No slots available for that date."
            }

        return {
            "status": "AVAILABLE",
            "slots": slots,
            "message": f"Found {len(slots)} available slot(s)."
        }

    except Exception as e:
        return {"status": "ERROR", "message": str(e), "slots": []}


def resolve_service_id(service_name: str) -> str | None:
    """
    Looks up a service ID by name (case-insensitive partial match).
    """
    try:
        result = supabase.table("services").select("id, name") \
            .ilike("name", f"%{service_name}%") \
            .limit(1).execute()
        if result.data:
            return result.data[0]["id"]
    except Exception:
        pass
    return None


def resolve_branch_id(branch_name: str) -> str | None:
    """
    Looks up a branch ID by name.
    """
    try:
        result = supabase.table("branches").select("id, name") \
            .ilike("name", f"%{branch_name}%") \
            .limit(1).execute()
        if result.data:
            return result.data[0]["id"]
    except Exception:
        pass
    return None