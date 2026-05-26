# SoCo Spa Reservation Confirmation Tool

A Python CLI program that crafts personalized reservation confirmation text messages from a template (for manual copy/paste sending) and automatically creates corresponding events in Google Calendar.

## Features

- Uses the provided `template` file (now with `$CONFIRMATION_DETAILS`)
- Interactive prompts for name, date, time, duration, **number of massages**, **couples massage (yes/no)**, and **massage type**
- Smart grammar engine that produces natural English:
  - `a 60-minute deep tissue massage`
  - `your two 60-minute Swedish massages`
  - `your 90-minute couples massage`
  - `your 60-minute hot stone couples massage`
- Optional **requested therapist** selected from a list:
  - Therapist name is appended to the message text ("... with Jane Doe")
  - Calendar title becomes `Jane Doe - Appt: Client Name`
  - Color is assigned automatically:
    - Couples massage → Sage
    - Specific therapist → Their configured default color
    - No therapist requested → Peacock (default blue)
- Renders the full confirmation message for easy copy/paste into any SMS app
- Creates Google Calendar event
- Event includes full confirmation text in description, correct start/end times (America/New_York timezone), and spa location
- `--dry-run` mode to preview everything without creating a calendar event
- **Strong conflict prevention**:
  - Enforces maximum concurrent *therapist usage* = number of therapists (currently 4)
  - A regular massage consumes 1 slot. A couples massage consumes **2 slots**.
  - "2 couples massages" = 4 therapist slots.
  - Prevents the same therapist from having overlapping bookings
  - Clear warnings + confirmation required to override
- Supports `.env` configuration for Google credentials paths

## Template

The message template lives in the `template` file next to the script. It now uses `$CONFIRMATION_DETAILS` (populated with smart grammar by the program):

```
Hi $NAME, thank you for choosing SoCo Spa! Here is your reservation confirmation for $TIME on $DATE for $CONFIRMATION_DETAILS. 

Our location is: 115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585. We are looking forward to seeing you!
```

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Google Calendar

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Google Calendar API**
4. Go to **APIs & Services > Credentials**
5. Create **OAuth 2.0 Client ID** → Application type: **Desktop app**
6. Download the JSON file and save it as `credentials.json` in this directory

   **Do not commit `credentials.json` or `.env` to git.**

7. (Optional) Copy `.env.example` to `.env` if you want to customize credential paths:
   ```bash
   cp .env.example .env
   # edit only if you renamed the json files
   ```

8. First run of the script will open a browser window for OAuth consent. Approve access to your Google Calendar.

### 3. Run the program

```bash
# Interactive mode (crafts message + creates calendar event)
python spa_reservation.py

# Preview only (no calendar write)
python spa_reservation.py --dry-run
```

During the run you will be prompted for:

- Customer name (the person the appointment is under)
- Number of massages (e.g. 1 or 2 when booking for friends)
- Is this a couples massage? (y/n)
- Massage type (deep tissue, Swedish, hot stone, etc. — optional)
- Requested therapist (selected from list: Yenni, Julie, Amy, Tracey, or none)
- Appointment date (`YYYYMMDD`)
- Appointment time (24-hour `HHMM`)
- Duration in minutes (per massage/session)

After crafting the message you will see the full text (ready to copy/paste into your phone's SMS app) plus a confirmation prompt before the calendar event is created.

## Example Sessions (Dry Run)

### Example 1: Two friends, deep tissue

```
SoCo Spa Reservation Confirmation
========================================
Customer name: Maria Lopez
Number of massages (default 1): 2
Is this a couples massage? (y/n, default n): n
Massage type (e.g. deep tissue, Swedish, hot stone - optional): deep tissue
Appointment date (YYYYMMDD): 20250415
Appointment time in 24-hour format (HHMM, e.g. 1430): 1500
Duration in minutes (e.g. 60): 60

Crafted confirmation message (copy this to send via your phone/SMS app):
--------------------------------------------------
Hi Maria Lopez, thank you for choosing SoCo Spa! Here is your reservation confirmation for 3:00 PM on April 15, 2025 for your two 60-minute deep tissue massages. 

Our location is: 115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585. We are looking forward to seeing you!
--------------------------------------------------

Calendar event title will be: Appt: Maria Lopez
Details: your two 60-minute deep tissue massages
Time: 3:00 PM on April 15, 2025 (60 minutes)

[DRY RUN] No calendar event created.
```

### Example 2: Couples massage

```
SoCo Spa Reservation Confirmation
========================================
Customer name: John & Sarah Patel
Number of massages (default 1): 1
Is this a couples massage? (y/n, default n): y
Massage type (e.g. deep tissue, Swedish, hot stone - optional): 
Appointment date (YYYYMMDD): 20250418
Appointment time in 24-hour format (HHMM, e.g. 1430): 1600
Duration in minutes (e.g. 60): 60

Crafted confirmation message (copy this to send via your phone/SMS app):
--------------------------------------------------
Hi John & Sarah Patel, thank you for choosing SoCo Spa! Here is your reservation confirmation for 4:00 PM on April 18, 2025 for your 60-minute couples massage. 

Our location is: 115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585. We are looking forward to seeing you!
--------------------------------------------------

Calendar event title will be: Appt: John & Sarah Patel
Details: your 60-minute couples massage
Time: 4:00 PM on April 18, 2025 (60 minutes)

[DRY RUN] No calendar event created.
```

### Example 3: With requested therapist (automatic color assignment)

```
SoCo Spa Reservation Confirmation
========================================
Customer name: Maria Lopez
Number of massages (default 1): 1
Is this a couples massage? (y/n, default n): n
Massage type (e.g. deep tissue, Swedish, hot stone - optional): deep tissue
Requested therapist:
  1. Yenni
  2. Julie
  3. Amy
  4. Tracey
  0. No specific therapist
Select number: 1
Appointment date (YYYYMMDD): 20250422
Appointment time in 24-hour format (HHMM, e.g. 1430): 1100
Duration in minutes (e.g. 60): 60

Crafted confirmation message (copy this to send via your phone/SMS app):
--------------------------------------------------
Hi Maria Lopez, thank you for choosing SoCo Spa! Here is your reservation confirmation for 11:00 AM on April 22, 2025 for a 60-minute deep tissue massage with Yenni. 

Our location is: 115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585. We are looking forward to seeing you!
--------------------------------------------------

Calendar event title will be: Yenni - Appt: Maria Lopez
Requested therapist: Yenni
Calendar color: Blueberry (ID 9)
Details: a 60-minute deep tissue massage with Yenni
Time: 11:00 AM on April 22, 2025 (60 minutes)

[DRY RUN] No calendar event created.
```

## Conflict Prevention (Important Rules)

The tool performs **thorough conflict checking** before allowing any booking:

**Rules enforced:**
- Maximum concurrent appointments at any time = number of therapists (currently 4).
- A specific therapist cannot have two overlapping appointments.

**How it works:**
- The tool queries your Google Calendar for the exact time window.
- It counts how many appointments are already scheduled during that period.
- If a specific therapist was requested, it also checks whether that therapist is already booked.
- If either the global capacity would be exceeded **or** the chosen therapist has a conflict, a clear warning is shown.
- You must explicitly type `y` to proceed anyway.

The calendar is the source of truth. These checks exist to prevent double bookings.

## Calendar Event

Created events have:

- **Title**:
  - No therapist requested: `Appt: Maria Lopez`
  - Therapist requested: `Jane Doe - Appt: Maria Lopez`
- **Color** (automatic):
  - Couples massage → Sage
  - Specific therapist → Their default color (configured in therapists.json)
  - No therapist requested → Peacock (default blue)
  - Manual overrides can be done directly in Google Calendar if needed
- **Location**: Spa address (from template)
- **Description**: Full confirmation message text (includes therapist when specified)
- **Time**: Correct start/end in America/New_York timezone
- **Source**: Your primary calendar (configurable via `GOOGLE_CALENDAR_ID`)

## Environment Variables

All can be set in `.env` or the shell environment (only needed for Google):

| Variable                    | Required | Default            | Description |
|-----------------------------|----------|--------------------|-------------|
| `GOOGLE_CREDENTIALS_FILE`   | No  | `credentials.json` | Path to OAuth client secrets |
| `GOOGLE_TOKEN_FILE`         | No  | `token.json`       | Where to store user token after first auth |
| `GOOGLE_CALENDAR_ID`        | No  | `primary`          | Calendar to write events to |

## Security Notes

- Never commit `.env`, `credentials.json`, or `token.json`
- The `.gitignore` already covers these files
- OAuth token is stored locally after first successful login

## Troubleshooting

- **Google auth errors**: Delete `token.json` and re-run to force fresh consent.
- **Time shows wrong**: Input uses 24-hour time; output is rendered in America/New_York.
- **No browser opens for login**: Run on a machine with a browser, or set up the token.json on another machine and copy it over.

## GUI Version (Recommended for Daily Use)

A graphical interface is available using Streamlit. It provides the same logic as the CLI with a much friendlier experience for the receptionists.

### Running the GUI

```bash
pip install -r requirements.txt
streamlit run spa_booking_gui.py
```

The GUI includes:
- Easy form inputs + optional notes for therapists
- Live preview of the message + calendar title + assigned color
- **Automatic conflict analysis** after submission (only flags real problems: capacity exceeded or same-therapist overlap)
- Different-therapist overlaps are shown as informational only
- Quick Availability View (next 5 hours of bookings)
- Creates one calendar event **per massage requested** (e.g., 3 massages → 3 events)
- Light description in calendar events (customer + therapist + notes). The full SMS message is shown in the GUI for copy-paste.

## Files

- `spa_reservation.py` — Main CLI tool
- `spa_booking_gui.py` — Streamlit GUI (recommended)
- `therapists.json` — List of therapists and their default colors
- `template` — Message template
- `requirements.txt` — Python dependencies
- `.env.example` — Template for secrets

## License

Internal tool for SoCo Spa.
