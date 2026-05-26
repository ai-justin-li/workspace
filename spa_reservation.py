#!/usr/bin/env python3
"""
SoCo Spa Reservation Confirmation Tool

- Reads the message template from ./template
- Collects reservation details from user input
- Crafts a personalized confirmation message (copy and send manually via phone)
- Supports optional requested therapist (included in message + title)
- If therapist requested: title becomes "TherapistName - Appt: Client", and user can pick a calendar color
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

# Google Calendar color options (shown only when a therapist is requested)
COLOR_CHOICES = [
    ("1", "Lavender"),
    ("2", "Sage"),
    ("3", "Grape"),
    ("4", "Flamingo"),
    ("5", "Banana"),
    ("6", "Tangerine"),
    ("7", "Peacock"),
    ("8", "Graphite"),
    ("9", "Blueberry"),
    ("10", "Basil"),
    ("11", "Tomato"),
]


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
    color_id: str | None = None,
    location: str = SPA_LOCATION,
) -> dict:
    """Create a Google Calendar event and return the created event resource.

    If therapist is provided, the title becomes "Jane Doe - Appt: Client Name".
    color_id is a Google Calendar colorId (e.g. "7" for Peacock).
    """
    service = get_calendar_service()

    summary = build_event_summary(name, therapist)

    event = {
        "summary": summary,
        "location": location,
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


def build_event_summary(name: str, therapist: str = "") -> str:
    """Build the Google Calendar event title.

    If a therapist is requested: "Jane Doe - Appt: Maria Lopez"
    Otherwise: "Appt: Maria Lopez"
    """
    if therapist:
        return f"{therapist} - Appt: {name}"
    return f"Appt: {name}"


def prompt_color_selection() -> str | None:
    """Show color menu and return a valid colorId (only called when therapist requested)."""
    print("\nTherapist requested — select a color for this calendar event:")
    for num, name in COLOR_CHOICES:
        print(f"  {num}. {name}")
    print("  (Press Enter for no special color)")
    choice = input("Color number: ").strip()
    if not choice:
        return None
    for num, _ in COLOR_CHOICES:
        if choice == num:
            return num
    print("  Invalid choice — no color will be applied.")
    return None


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

    therapist = input("Requested therapist (optional - leave blank if none): ").strip()

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

    # Build grammatically correct confirmation phrase
    confirmation_details = build_confirmation_details(
        num_massages, is_couples, mtype, display_duration, therapist
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
        "therapist": therapist,
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

    therapist = details.get("therapist", "")
    event_title = build_event_summary(details["name"], therapist)

    print("\nCrafted confirmation message (copy this to send via your phone/SMS app):")
    print("-" * 50)
    print(details["message"])
    print("-" * 50)

    print(f"\nCalendar event title will be: {event_title}")
    if therapist:
        print(f"Requested therapist: {therapist}")
    print(f"Details: {details['confirmation_details']}")
    print(f"Time: {details['display_time']} on {details['display_date']} ({details['duration_minutes']} minutes)")

    if args.dry_run:
        print("\n[DRY RUN] No calendar event created.")
        return

    color_id = None
    if therapist:
        color_id = prompt_color_selection()

    confirm = input("\nCreate the Google Calendar event now? (y/N): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Cancelled. No calendar event created.")
        return

    # Create Calendar event
    try:
        event = create_calendar_event(
            name=details["name"],
            description=details["message"],
            start_dt=details["start_dt"],
            end_dt=details["end_dt"],
            therapist=therapist,
            color_id=color_id,
        )
        event_link = event.get("htmlLink", "No link available")
        print(f"\nGoogle Calendar event created: {event_link}")
        print(f"Event ID: {event.get('id')}")
        if color_id:
            print(f"Color ID applied: {color_id}")
    except Exception as e:
        print(f"Failed to create calendar event: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nReservation processing complete.")


if __name__ == "__main__":
    main()
