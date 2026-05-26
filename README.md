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
- Optional **requested therapist**:
  - Therapist name is appended to the message text ("... with Jane Doe")
  - Calendar title becomes `Jane Doe - Appt: Client Name`
  - User can choose a Google Calendar color for the event (Lavender, Peacock, Tomato, etc.)
- Renders the full confirmation message for easy copy/paste into any SMS app
- Creates Google Calendar event
- Event includes full confirmation text in description, correct start/end times (America/New_York timezone), and spa location
- `--dry-run` mode to preview everything without creating a calendar event
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
- Requested therapist (optional — e.g. "Jane Doe")
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

### Example 3: With requested therapist (color selection enabled)

```
SoCo Spa Reservation Confirmation
========================================
Customer name: Maria Lopez
Number of massages (default 1): 1
Is this a couples massage? (y/n, default n): n
Massage type (e.g. deep tissue, Swedish, hot stone - optional): deep tissue
Requested therapist (optional - leave blank if none): Jane Doe
Appointment date (YYYYMMDD): 20250422
Appointment time in 24-hour format (HHMM, e.g. 1430): 1100
Duration in minutes (e.g. 60): 60

Crafted confirmation message (copy this to send via your phone/SMS app):
--------------------------------------------------
Hi Maria Lopez, thank you for choosing SoCo Spa! Here is your reservation confirmation for 11:00 AM on April 22, 2025 for a 60-minute deep tissue massage with Jane Doe. 

Our location is: 115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585. We are looking forward to seeing you!
--------------------------------------------------

Calendar event title will be: Jane Doe - Appt: Maria Lopez
Requested therapist: Jane Doe
Details: a 60-minute deep tissue massage with Jane Doe
Time: 11:00 AM on April 22, 2025 (60 minutes)

(At this point the program would show the color selection menu because a therapist was requested)

[DRY RUN] No calendar event created.
```

## Calendar Event

Created events have:

- **Title**:
  - No therapist requested: `Appt: Maria Lopez`
  - Therapist requested: `Jane Doe - Appt: Maria Lopez`
- **Color** (optional): When a therapist is requested, you can choose one of 11 Google Calendar colors (Lavender, Sage, Peacock, Tomato, etc.)
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

## Files

- `spa_reservation.py` — Main CLI tool
- `template` — Message template (edit as needed)
- `requirements.txt` — Python dependencies
- `.env.example` — Template for secrets

## License

Internal tool for SoCo Spa.
