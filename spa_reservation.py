#!/usr/bin/env python3
"""
SoCo Spa Reservation Confirmation Tool

- Reads the message template from ./template
- Collects reservation details from user input
- Crafts a personalized confirmation message (copy and send manually via phone)
- Supports optional requested therapist selected from a list (included in message + title)
- Calendar color is assigned automatically:
    - Couples massage → Sage
    - Specific therapist → Their default color
    - No therapist requested → Peacock (default blue)
- Creates a corresponding event in Google Calendar

Usage:
  python spa_reservation.py
  python spa_reservation.py --dry-run

Prerequisites:
  - pip install -r requirements.txt
  - Place Google OAuth credentials.json in this directory (first run will open browser)
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

# Load environment variables from .env if present (optional dependency for convenience)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Constants
TEMPLATE_PATH = Path(__file__).parent / "template"
DEFAULT_TIMEZONE = "America/New_York"
SPA_LOCATION = "115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585"

# Google config (loaded from .env or environment if present)
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")

# Path to therapists configuration
THERAPISTS_FILE = Path(__file__).parent / "therapists.json"


def get_calendar_service():
    """Authenticate and return a Google Calendar API service client."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

    creds = None
    token_path = GOOGLE_TOKEN_FILE

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Google credentials file not found: {GOOGLE_CREDENTIALS_FILE}\n"
                    "Download OAuth 2.0 Client ID (Desktop) credentials from "
                    "Google Cloud Console and save as credentials.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    return service


def create_calendar_event(
    name: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime,
    therapist: str = "",
    num_massages: int = 1,
    duration_minutes: int = 60,
    is_couples: bool = False,
    notes: str = "",
    is_returning: bool = False,
    color_id: str | None = None,
    location: str = SPA_LOCATION,
) -> dict:
    """Create a Google Calendar event and return the created event resource.

    Colors:
    - Couples or exactly 2 massages → Sage
    - More than 2 massages → Basil
    - Otherwise → therapist default or Peacock

    Title examples:
    - "大力 Appt: 90x2 Alex"   (2 massages, 90min, note "大力")
    - "脚 Appt: 60x3 Alex"     (3 massages, 60min, note "脚")
    - "Appt: 120C Alex"        (120min couples)
    """
    service = get_calendar_service()

    summary = build_event_summary(name, num_massages, duration_minutes or 60, is_couples, notes, is_returning)

    event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": DEFAULT_TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": DEFAULT_TIMEZONE,
        },
    }

    if color_id:
        event["colorId"] = color_id

    created_event = (
        service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
    )
    return created_event


def format_display_time(dt: datetime) -> str:
    """Return human-friendly time like '2:00 PM' (no leading zero)."""
    hour = dt.hour
    minute = dt.minute
    ampm = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {ampm}"


def format_display_date(d: datetime.date) -> str:
    """Return human-friendly date like 'April 10, 2025'."""
    return d.strftime("%B %d, %Y")


def number_to_words(n: int) -> str:
    """Convert small integers to English words for natural grammar."""
    words = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
        11: "eleven",
        12: "twelve",
    }
    return words.get(n, str(n))


def build_confirmation_details(
    num_massages: int,
    is_couples: bool,
    massage_type: str,
    display_duration: str,
    therapist: str = "",
) -> str:
    """Build a grammatically correct confirmation phrase.

    Duration always precedes the type for natural English.
    If a therapist is requested, appends " with Therapist Name".

    Examples:
      - "a 60-minute deep tissue massage"
      - "your two 60-minute deep tissue massages with Jane Doe"
      - "your 60-minute couples massage"
      - "your 90-minute hot stone couples massage with Michael"
    """
    mtype = massage_type.strip() if massage_type else ""

    if is_couples:
        if mtype:
            phrase = f"your {display_duration} {mtype} couples massage"
        else:
            phrase = f"your {display_duration} couples massage"
    elif num_massages <= 1:
        if mtype:
            phrase = f"a {display_duration} {mtype} massage"
        else:
            phrase = f"a {display_duration} massage"
    else:
        num_word = number_to_words(num_massages)
        if mtype:
            phrase = f"your {num_word} {display_duration} {mtype} massages"
        else:
            phrase = f"your {num_word} {display_duration} massages"

    if therapist:
        phrase += f" with {therapist}"
    return phrase


def build_event_summary(name: str, num_massages: int = 1, duration_minutes: int = 60, is_couples: bool = False, notes: str = "", is_returning: bool = False) -> str:
    """Build the Google Calendar event title.

    Examples:
    - "大力 Appt: 90x2 Alex"   (2 massages, 90min + note "大力")
    - "脚 Appt: 60x3 Alex"     (3 massages, 60min + note "脚")
    - "Appt: 120C Alex"        (120min couples)
    - "Appt: 60x2 Alex r"      (returning customer)
    """
    prefix = f"{notes} " if notes else ""

    if is_couples:
        base = f"Appt: {duration_minutes}C {name}"
    elif num_massages > 1:
        base = f"Appt: {duration_minutes}x{num_massages} {name}"
    else:
        base = f"Appt: {name}"

    suffix = " r" if is_returning else ""
    return prefix + base + suffix


def get_upcoming_events(hours: int = 12):
    """
    Return a list of upcoming events in the next N hours.
    Each item has:
      - time: human readable time range (e.g. "2:00 PM – 3:00 PM")
      - summary: event title
    """
    try:
        service = get_calendar_service()
        now = datetime.now(ZoneInfo("America/New_York"))
        time_max = now + timedelta(hours=hours)

        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        upcoming = []

        for event in events:
            summary = event.get('summary', 'Untitled Event')
            start = event['start'].get('dateTime')
            end = event['end'].get('dateTime')

            if start and end:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(ZoneInfo("America/New_York"))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00')).astimezone(ZoneInfo("America/New_York"))

                time_str = f"{start_dt.strftime('%-I:%M %p')} – {end_dt.strftime('%-I:%M %p')}"
            else:
                time_str = "All day"

            upcoming.append({
                "time": time_str,
                "summary": summary
            })

        return upcoming

    except Exception as e:
        print(f"Error fetching upcoming events: {e}")
        return []


def get_calendar_events(start_date: str, end_date: str):
    """
    Fetch events between two dates (YYYY-MM-DD format, interpreted in America/New_York).
    Returns list of events with date, time range, and summary.
    """
    try:
        service = get_calendar_service()
        tz = ZoneInfo(DEFAULT_TIMEZONE)
        # Start at local midnight on start_date
        time_min = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=tz).isoformat()
        # End at local midnight the day after end_date (standard way to include full end_date)
        time_max = (datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=tz) + timedelta(days=1)).isoformat()

        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        result = []

        for event in events:
            summary = event.get('summary', 'Untitled Event')
            start = event['start'].get('dateTime')
            end = event['end'].get('dateTime')

            if start and end:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(ZoneInfo("America/New_York"))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00')).astimezone(ZoneInfo("America/New_York"))

                date_str = start_dt.strftime('%Y-%m-%d')
                time_str = f"{start_dt.strftime('%-I:%M %p')} – {end_dt.strftime('%-I:%M %p')}"
                start_hour = start_dt.hour
                start_minute = start_dt.minute
                end_hour = end_dt.hour
                end_minute = end_dt.minute
            else:
                date_str = start_date
                time_str = "All day"
                start_hour = None
                start_minute = 0
                end_hour = None
                end_minute = 0

            result.append({
                "date": date_str,
                "time": time_str,
                "summary": summary,
                "id": event.get('id'),
                "htmlLink": event.get('htmlLink'),
                "colorId": event.get('colorId'),
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute
            })

        return result

    except Exception as e:
        print(f"Error fetching calendar events: {e}")
        return []


def load_therapists() -> list[dict]:
    """Load the list of therapists from therapists.json."""
    if not THERAPISTS_FILE.exists():
        raise FileNotFoundError(
            f"Therapists file not found: {THERAPISTS_FILE}\n"
            "Please create therapists.json with the list of available therapists."
        )
    import json
    with open(THERAPISTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_color_name(color_id: str) -> str:
    """Return a human-friendly name for a Google Calendar color ID."""
    color_names = {
        "1": "Lavender",
        "2": "Sage",
        "3": "Grape",
        "4": "Flamingo",
        "5": "Banana",
        "6": "Tangerine",
        "7": "Peacock",
        "8": "Graphite",
        "9": "Blueberry",
        "10": "Basil",
        "11": "Tomato",
    }
    return color_names.get(color_id, f"Color {color_id}")


def _get_therapist_slots_from_summary(summary: str) -> int:
    """
    Parse a calendar event title to determine how many therapist slots it consumes.

    This relies on the title (summary) because titles are formatted to encode
    booking size (xN for multiple massages, C for couples).
    """
    if not summary:
        return 1

    # Look for "Appt xN" pattern (case insensitive)
    match = re.search(r'Appt x(\d+)', summary, re.IGNORECASE)
    if match:
        n = int(match.group(1))
        # If the title mentions couples, each unit costs 2 therapists
        if 'couples' in summary.lower():
            return n * 2
        return n

    # Legacy or single booking
    if 'couples' in summary.lower():
        return 2

    return 1


def _get_assigned_therapist_from_description(description: str) -> str | None:
    """
    Extract the assigned therapist name from the calendar event's description (notes).

    The description is formatted as:
        Customer: ...
        Therapist: Julie
        Notes: ...

    Returns the therapist name, or None if not specified / Unassigned.
    This is the authoritative source for "which therapist" an existing booking uses.
    """
    if not description:
        return None
    match = re.search(r'Therapist:\s*([^\n\r]+)', description, re.IGNORECASE)
    if not match:
        return None
    name = match.group(1).strip()
    if not name or name.lower() in ('unassigned', 'none', ''):
        return None
    return name


def analyze_booking_conflicts(start_dt, end_dt, requested_therapist_name=None, num_massages=1, is_couples=False):
    """
    Thoroughly analyze potential conflicts for a new booking.

    Rules:
    - Maximum concurrent therapist usage <= number of therapists (global capacity)
    - Same therapist cannot have overlapping appointments

    Therapist usage calculation:
    - Regular massage: 1 slot per massage
    - Couples massage: 2 slots per massage

    So a booking for 2 couples massages consumes 4 therapist slots.

    Overlaps with *different* therapists are acceptable as long as total capacity is not exceeded.

    Important:
    - Slot counts (for capacity) are parsed from the event **title** (summary), which encodes
      multiplicity via "Appt xN" or "couples".
    - Specific therapist assignment (for per-therapist conflicts) is read from the event
      **description** (notes field), which contains "Therapist: Name".
      We deliberately do NOT scan titles for therapist names, because client names
      can match therapist names (e.g. a customer named "Julie").

    Returns a rich analysis dict.
    """
    therapists = load_therapists()
    max_capacity = len(therapists)

    # Calculate how many therapist slots this booking will consume
    slots_per_massage = 2 if is_couples else 1
    booking_slots = num_massages * slots_per_massage

    try:
        service = get_calendar_service()
        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        conflicts = []

        for event in events:
            summary = event.get('summary', 'Untitled Event')
            description = event.get('description', '')
            start = event['start'].get('dateTime', event['start'].get('date'))
            html_link = event.get('htmlLink', '')

            conflicts.append({
                'summary': summary,
                'description': description,
                'start': start,
                'htmlLink': html_link
            })

        # Enrich with assigned therapist (read from description/notes, not title)
        for c in conflicts:
            c['assigned_therapist'] = _get_assigned_therapist_from_description(c.get('description', ''))

        # Calculate actual therapist slots currently in use by parsing titles
        # (titles encode xN / couples size; therapist identity comes from description)
        current_slots_used = sum(
            _get_therapist_slots_from_summary(c['summary']) for c in conflicts
        )

        capacity_violation = (current_slots_used + booking_slots) > max_capacity

        therapist_conflict = False
        conflicting_therapist = None

        if requested_therapist_name:
            # Check using the therapist assigned in the event's description (notes),
            # NOT by scanning the title/summary (client names can match therapist names).
            for event in conflicts:
                assigned = event.get('assigned_therapist')
                if assigned and assigned.lower() == requested_therapist_name.lower():
                    therapist_conflict = True
                    conflicting_therapist = requested_therapist_name
                    break

        # Categorize issues
        hard_conflict = capacity_violation or therapist_conflict

        messages = []
        if capacity_violation:
            messages.append(
                f"Capacity violation: This booking uses {booking_slots} therapist slots. "
                f"Current load: {current_slots_used}/{max_capacity}."
            )
        if therapist_conflict:
            messages.append(
                f"Therapist conflict: {requested_therapist_name} already has an appointment at this time."
            )
        if not hard_conflict and conflicts:
            messages.append(
                f"{len(conflicts)} other appointment(s) overlap this time slot (different therapists - OK)."
            )

        return {
            'conflicts': conflicts,
            'capacity_violation': capacity_violation,
            'therapist_conflict': therapist_conflict,
            'hard_conflict': hard_conflict,
            'current_slots_used': current_slots_used,
            'max_capacity': max_capacity,
            'booking_slots': booking_slots,
            'conflicting_therapist': conflicting_therapist,
            'message': " | ".join(messages) if messages else "No conflicts detected.",
            'is_clear': not hard_conflict
        }

    except Exception as e:
        print(f"\nWarning: Unable to check calendar for conflicts ({e}).")
        print("Proceeding without conflict check.\n")
        return {
            'conflicts': [],
            'capacity_violation': False,
            'therapist_conflict': False,
            'hard_conflict': False,
            'current_slots_used': 0,
            'max_capacity': max_capacity,
            'booking_slots': booking_slots,
            'conflicting_therapist': None,
            'message': "Conflict check failed - please verify manually.",
            'is_clear': True
        }


def collect_reservation_details() -> dict:
    """Interactively collect reservation details and return structured data + rendered message."""
    print("SoCo Spa Reservation Confirmation")
    print("=" * 40)

    name = input("Customer name: ").strip()
    if not name:
        raise ValueError("Name is required.")

    # New inputs for number of people, couples, and massage type
    num_input = input("Number of massages (default 1): ").strip() or "1"
    try:
        num_massages = max(1, int(num_input))
    except ValueError:
        num_massages = 1

    couples_str = input("Is this a couples massage? (y/n, default n): ").strip().lower() or "n"
    is_couples = couples_str in ("y", "yes", "true")

    mtype = input("Massage type (e.g. deep tissue, Swedish, hot stone - optional): ").strip()

    # Therapist selection (loaded from therapists.json)
    therapists = load_therapists()
    print("\nRequested therapist:")
    for i, t in enumerate(therapists, 1):
        print(f"  {i}. {t['name']}")
    print("  0. No specific therapist")

    while True:
        choice = input("Select number: ").strip()
        if choice == "0" or choice == "":
            therapist = None
            break
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(therapists):
                therapist = therapists[idx]
                break
        except ValueError:
            pass
        print("  Invalid selection. Please choose a number from the list.")

    is_returning = input("Is this a returning customer? (y/N): ").strip().lower() in ("y", "yes")

    date_input = input("Appointment date (YYYYMMDD): ").strip()
    time_input = input("Appointment time in 24-hour format (HHMM, e.g. 1430): ").strip()
    duration_input = input("Duration in minutes (e.g. 60): ").strip()

    try:
        appt_date = datetime.strptime(date_input, "%Y%m%d").date()
        appt_time = datetime.strptime(time_input, "%H%M").time()
        duration_minutes = int(duration_input)
        if duration_minutes <= 0:
            raise ValueError("Duration must be positive.")
    except ValueError as e:
        raise ValueError(f"Invalid date/time/duration input: {e}") from e

    tz = ZoneInfo(DEFAULT_TIMEZONE)
    start_dt = datetime.combine(appt_date, appt_time, tzinfo=tz)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    display_date = format_display_date(appt_date)
    display_time = format_display_time(start_dt)
    display_duration = f"{duration_minutes}-minute"

    # Therapist name for message (if selected)
    therapist_name = therapist["name"] if therapist else ""

    # Build grammatically correct confirmation phrase
    confirmation_details = build_confirmation_details(
        num_massages, is_couples, mtype, display_duration, therapist_name
    )

    # Load and render template
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template file not found: {TEMPLATE_PATH}")

    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    t = Template(template_text)
    message = t.safe_substitute(
        NAME=name,
        TIME=display_time,
        DATE=display_date,
        CONFIRMATION_DETAILS=confirmation_details,
    )

    return {
        "name": name,
        "message": message,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "duration_minutes": duration_minutes,
        "display_date": display_date,
        "display_time": display_time,
        "num_massages": num_massages,
        "is_couples": is_couples,
        "massage_type": mtype,
        "therapist": therapist,           # dict or None
        "therapist_name": therapist_name, # string for display
        "is_returning": is_returning,
        "confirmation_details": confirmation_details,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Craft a reservation confirmation message from the template and create a Google Calendar event."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Craft and display the message but do not create a calendar event.",
    )
    args = parser.parse_args()

    try:
        details = collect_reservation_details()
    except Exception as e:
        print(f"Error collecting inputs: {e}", file=sys.stderr)
        sys.exit(1)

    therapist = details.get("therapist")  # dict or None
    therapist_name = details.get("therapist_name", "")
    event_title = build_event_summary(
        details["name"], 
        details.get("num_massages", 1), 
        details.get("duration_minutes", 60), 
        details.get("is_couples", False), 
        details.get("notes", ""),
        details.get("is_returning", False)
    )

    print("\nCrafted confirmation message (copy this to send via your phone/SMS app):")
    print("-" * 50)
    print(details["message"])
    print("-" * 50)

    print(f"\nCalendar event title will be: {event_title}")
    if therapist_name:
        print(f"Requested therapist: {therapist_name}")

    # Determine color automatically
    # Sage for all 2-person massages (couples or exactly 2 massages)
    # Basil for more than 2 massages
    num_massages = details.get("num_massages", 1)
    is_couples = details.get("is_couples", False)
    if is_couples or num_massages == 2:
        color_id = "2"   # Sage
    elif num_massages > 2:
        color_id = "10"  # Basil
    elif therapist:
        color_id = therapist.get("default_color", "7")
    else:
        color_id = "7"   # Peacock - default when no therapist requested

    color_name = get_color_name(color_id)
    print(f"Calendar color: {color_name} (ID {color_id})")

    print(f"Details: {details['confirmation_details']}")
    print(f"Time: {details['display_time']} on {details['display_date']} ({details['duration_minutes']} minutes)")

    if args.dry_run:
        print("\n[DRY RUN] No calendar event created.")
        return

    confirm = input("\nCreate the Google Calendar event now? (y/N): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Cancelled. No calendar event created.")
        return

    # === Thorough double-booking prevention check ===
    analysis = analyze_booking_conflicts(
        details["start_dt"],
        details["end_dt"],
        requested_therapist_name=therapist_name if therapist_name else None,
        num_massages=details.get("num_massages", 1),
        is_couples=details.get("is_couples", False),
    )

    if analysis.get('hard_conflict') or analysis['conflicts']:
        print("\n" + "=" * 60)
        print("⚠️  BOOKING CONFLICT ANALYSIS")
        print("=" * 60)

        current_used = analysis.get('current_slots_used', analysis.get('current_concurrent', 0))
        print(f"Current therapist usage in this time window: {current_used}")
        print(f"Maximum allowed:                             {analysis['max_capacity']}")
        print(f"This booking will use:                       {analysis.get('booking_slots', 1)} therapist slots")

        if analysis.get('capacity_violation'):
            print("\n❌ CAPACITY VIOLATION")
            slots = analysis.get('booking_slots', 1)
            current_used = analysis.get('current_slots_used', analysis.get('current_concurrent', 0))
            print(f"   This booking uses {slots} therapist slots.")
            print(f"   Current load: {current_used}/{analysis['max_capacity']}. Would exceed limit.")

        if analysis.get('therapist_conflict'):
            print(f"\n❌ THERAPIST CONFLICT")
            print(f"   {analysis.get('conflicting_therapist')} is already booked during this time.")

        if analysis['conflicts']:
            if analysis.get('hard_conflict'):
                print("\nConflicting appointments:")
            else:
                print("\nOther appointments in this time slot (different therapists — acceptable):")

            for c in analysis['conflicts']:
                ther = c.get('assigned_therapist')
                ther_str = f" [Therapist: {ther}]" if ther else ""
                print(f"  • {c['summary']}{ther_str}")
                print(f"    Starts: {c['start']}")
                if c.get('htmlLink'):
                    print(f"    Link:   {c['htmlLink']}")

        print("\n" + analysis['message'])
        print("\nThe calendar is the source of truth. Double bookings are not allowed.")
        print("=" * 60)

        override = input("\nProceed with this booking anyway? (y/N): ").strip().lower()
        if override not in ("y", "yes"):
            print("Booking cancelled.")
            return

    # Create exactly one calendar event (even for multiple massages)
    # Title will indicate quantity (e.g. "Appt x3: John")
    light_description = f"Customer: {details['name']}\nTherapist: {therapist_name or 'Unassigned'}\nNotes: -"

    try:
        event = create_calendar_event(
            name=details["name"],
            description=light_description,
            start_dt=details["start_dt"],
            end_dt=details["end_dt"],
            therapist=therapist_name,
            num_massages=details.get("num_massages", 1),
            duration_minutes=details.get("duration_minutes", 60),
            is_couples=details.get("is_couples", False),
            notes=details.get("notes", ""),
            is_returning=details.get("is_returning", False),
            color_id=color_id,
        )

        print(f"\nGoogle Calendar event created: {event.get('htmlLink')}")
        print(f"Event ID: {event.get('id')}")
        print(f"Color applied: {color_name}")

    except Exception as e:
        print(f"Failed to create calendar event: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nReservation processing complete.")


if __name__ == "__main__":
    main()
