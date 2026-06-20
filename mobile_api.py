"""
Mobile-friendly API for SoCo Spa Booking.

This provides clean endpoints that a phone-optimized web app (or future chatbot/voice AI)
can call. All the important business logic (conflict checking, title generation, etc.)
remains in spa_reservation.py.

Run locally:
    uvicorn mobile_api:app --reload --host 0.0.0.0 --port 8000

For remote access:
- Use Cloudflare Tunnel: cloudflared tunnel --url http://localhost:8000
- Then access: https://your-tunnel.trycloudflare.com/mobile/

Note: Authentication is currently disabled.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from spa_reservation import (
    load_therapists,
    build_confirmation_details,
    build_event_summary,
    get_color_name,
    analyze_booking_conflicts,
    create_calendar_event,
)

app = FastAPI(title="SoCo Spa Mobile API")

# Allow calls from phones / future frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---

class BookingRequest(BaseModel):
    name: str
    num_massages: int = 1
    is_couples: bool = False
    is_returning: bool = False
    massage_type: str = ""
    therapist_name: str = ""          # empty string = no specific therapist
    date_str: str                     # YYYYMMDD
    time_str: str                     # HHMM
    duration_minutes: int = 60
    notes: str = ""

class ConflictAnalysisResponse(BaseModel):
    is_clear: bool
    hard_conflict: bool
    capacity_violation: bool
    therapist_conflict: bool
    current_slots_used: int
    max_capacity: int
    booking_slots: int
    conflicts: list
    message: str

class CreateBookingResponse(BaseModel):
    success: bool
    message: str
    event_link: Optional[str] = None
    event_id: Optional[str] = None


# --- Endpoints ---

@app.get("/therapists")
def get_therapists():
    """Return the list of available therapists for the dropdown."""
    return load_therapists()


@app.post("/analyze", response_model=ConflictAnalysisResponse)
def analyze_booking(request: BookingRequest):
    """Run the full conflict analysis before creating a booking."""
    try:
        # Parse date/time
        appt_date = datetime.strptime(request.date_str, "%Y%m%d").date()
        appt_time = datetime.strptime(request.time_str, "%H%M").time()
        tz = ZoneInfo("America/New_York")
        start_dt = datetime.combine(appt_date, appt_time, tzinfo=tz)
        end_dt = start_dt + __import__("datetime").timedelta(minutes=request.duration_minutes)

        analysis = analyze_booking_conflicts(
            start_dt=start_dt,
            end_dt=end_dt,
            requested_therapist_name=request.therapist_name if request.therapist_name else None,
            num_massages=request.num_massages,
            is_couples=request.is_couples,
        )
        return analysis

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")


@app.post("/create", response_model=CreateBookingResponse)
def create_booking(request: BookingRequest):
    """Create the reservation (one event with correct title formatting)."""
    try:
        # Parse date/time
        appt_date = datetime.strptime(request.date_str, "%Y%m%d").date()
        appt_time = datetime.strptime(request.time_str, "%H%M").time()
        tz = ZoneInfo("America/New_York")
        start_dt = datetime.combine(appt_date, appt_time, tzinfo=tz)
        end_dt = start_dt + __import__("datetime").timedelta(minutes=request.duration_minutes)

        # First run analysis to be safe
        analysis = analyze_booking_conflicts(
            start_dt=start_dt,
            end_dt=end_dt,
            requested_therapist_name=request.therapist_name if request.therapist_name else None,
            num_massages=request.num_massages,
            is_couples=request.is_couples,
        )

        if analysis["hard_conflict"]:
            return CreateBookingResponse(
                success=False,
                message=f"Booking blocked due to conflict: {analysis['message']}"
            )

        # Build the inner phrase + full message for notes
        display_date = appt_date.strftime("%B %d, %Y")
        display_time = start_dt.strftime("%-I:%M %p")
        display_duration = f"{request.duration_minutes}-minute"

        confirmation_details = build_confirmation_details(
            request.num_massages,
            request.is_couples,
            request.massage_type,
            display_duration,
            request.therapist_name,
        )

        # Build the full message (for reference only - not put in calendar)
        from pathlib import Path
        from string import Template
        TEMPLATE_PATH = Path(__file__).parent / "template"
        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        t = Template(template_text)
        full_message = t.safe_substitute(
            NAME=request.name,
            TIME=display_time,
            DATE=display_date,
            CONFIRMATION_DETAILS=confirmation_details,
        )
        # Notes are *not* included in the customer SMS (they are for internal use only).
        # They are stored in the calendar description and used as a prefix on the event title.

        # Determine color:
        # Sage for all 2-person massages (couples or exactly 2 massages)
        # Basil for more than 2 massages
        if request.is_couples or request.num_massages == 2:
            color_id = "2"   # Sage
        elif request.num_massages > 2:
            color_id = "10"  # Basil
        elif request.therapist_name:
            therapists = load_therapists()
            therapist_obj = next((t for t in therapists if t["name"] == request.therapist_name), None)
            color_id = therapist_obj["default_color"] if therapist_obj else "7"
        else:
            color_id = "7"   # Peacock

        # Light description for the calendar
        description = (
            f"Customer: {request.name}\n"
            f"Therapist: {request.therapist_name or 'Unassigned'}\n"
            f"Notes: {request.notes or '-'}"
        )

        # Create the event
        event = create_calendar_event(
            name=request.name,
            description=description,
            start_dt=start_dt,
            end_dt=end_dt,
            therapist=request.therapist_name,
            num_massages=request.num_massages,
            duration_minutes=request.duration_minutes,
            is_couples=request.is_couples,
            is_returning=request.is_returning,
            notes=request.notes,
            color_id=color_id,
        )

        return CreateBookingResponse(
            success=True,
            message="Reservation created successfully.",
            event_link=event.get("htmlLink"),
            event_id=event.get("id"),
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create booking: {str(e)}")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/availability")
def get_availability(hours: int = 12):
    """Return upcoming events for the availability view."""
    from spa_reservation import get_upcoming_events
    events = get_upcoming_events(hours)
    return {"events": events, "hours": hours}


@app.get("/calendar")
def get_calendar(start: str, end: str):
    """
    Return events for a date range.
    Query params: start=YYYY-MM-DD, end=YYYY-MM-DD
    """
    from spa_reservation import get_calendar_events
    try:
        events = get_calendar_events(start, end)
        return {"events": events, "start": start, "end": end}
    except Exception as e:
        return {"events": [], "start": start, "end": end, "error": str(e)}


# Serve the mobile web app
app.mount("/mobile", StaticFiles(directory="static/mobile", html=True), name="mobile")

# Redirect root to the mobile app for convenience
from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/mobile/")
