#!/usr/bin/env python3
"""
SoCo Spa Reservation Confirmation Tool

- Reads the message template from ./template
- Collects reservation details from user input
- Crafts a personalized confirmation SMS
- Sends the SMS via Twilio
- Creates a corresponding event in Google Calendar titled "Appt: $NAME"

Usage:
  python spa_reservation.py
  python spa_reservation.py --dry-run

Prerequisites:
  - pip install -r requirements.txt
  - Configure .env with Twilio credentials
  - Place Google OAuth credentials.json in this directory (first run will open browser)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Constants
TEMPLATE_PATH = Path(__file__).parent / "template"
DEFAULT_TIMEZONE = "America/New_York"
SPA_LOCATION = "115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585"

# Twilio config
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_PHONE = os.getenv("TWILIO_FROM_PHONE")

# Google config
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")


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


def send_sms(to_phone: str, body: str) -> str:
    """Send SMS via Twilio and return the message SID."""
    from twilio.rest import Client

    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_PHONE]):
        raise ValueError(
            "Missing Twilio credentials. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "and TWILIO_FROM_PHONE in your environment or .env file."
        )

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        to=to_phone,
        from_=TWILIO_FROM_PHONE,
        body=body,
    )
    return message.sid


def create_calendar_event(
    name: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime,
    location: str = SPA_LOCATION,
) -> dict:
    """Create a Google Calendar event and return the created event resource."""
    service = get_calendar_service()

    event = {
        "summary": f"Appt: {name}",
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


def collect_reservation_details() -> dict:
    """Interactively collect all required inputs and return structured data."""
    print("SoCo Spa Reservation Confirmation")
    print("=" * 40)

    name = input("Customer name: ").strip()
    if not name:
        raise ValueError("Name is required.")

    phone = input("Phone number in E.164 format (e.g. +18435551212): ").strip()
    if not phone.startswith("+") or not phone[1:].isdigit():
        print("Warning: Phone number should start with + and contain only digits.")
        print("Example: +18435551212 for US number.")

    date_input = input("Appointment date (YYYY-MM-DD): ").strip()
    time_input = input("Appointment time in 24-hour format (HH:MM, e.g. 14:30): ").strip()
    duration_input = input("Duration in minutes (e.g. 60): ").strip()

    try:
        appt_date = datetime.strptime(date_input, "%Y-%m-%d").date()
        appt_time = datetime.strptime(time_input, "%H:%M").time()
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

    # Load and render template
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template file not found: {TEMPLATE_PATH}")

    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    t = Template(template_text)
    message = t.safe_substitute(
        NAME=name,
        TIME=display_time,
        DATE=display_date,
        DURATION=display_duration,
    )

    return {
        "name": name,
        "phone": phone,
        "message": message,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "duration_minutes": duration_minutes,
        "display_date": display_date,
        "display_time": display_time,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Craft and send reservation confirmation SMS, then create Google Calendar event."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Craft and display the message but do not send SMS or create calendar event.",
    )
    args = parser.parse_args()

    try:
        details = collect_reservation_details()
    except Exception as e:
        print(f"Error collecting inputs: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nCrafted confirmation message:")
    print("-" * 50)
    print(details["message"])
    print("-" * 50)
    print(f"\nWill send to: {details['phone']}")
    print(f"Calendar event title: Appt: {details['name']}")
    print(f"Time: {details['display_time']} on {details['display_date']} ({details['duration_minutes']} minutes)")

    if args.dry_run:
        print("\n[DRY RUN] No SMS sent. No calendar event created.")
        return

    confirm = input("\nProceed to send SMS and create calendar event? (y/N): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Cancelled. No messages sent, no events created.")
        return

    # Send SMS
    try:
        sid = send_sms(details["phone"], details["message"])
        print(f"\nSMS sent successfully. Twilio SID: {sid}")
    except Exception as e:
        print(f"Failed to send SMS: {e}", file=sys.stderr)
        # Continue to calendar? Or exit. For now continue so partial work isn't lost.
        print("Continuing to calendar creation...")

    # Create Calendar event
    try:
        event = create_calendar_event(
            name=details["name"],
            description=details["message"],
            start_dt=details["start_dt"],
            end_dt=details["end_dt"],
        )
        event_link = event.get("htmlLink", "No link available")
        print(f"Google Calendar event created: {event_link}")
        print(f"Event ID: {event.get('id')}")
    except Exception as e:
        print(f"Failed to create calendar event: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nReservation processing complete.")


if __name__ == "__main__":
    main()
