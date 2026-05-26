# SoCo Spa Reservation Confirmation Tool

A Python CLI program that crafts personalized reservation confirmation text messages from a template, sends them via SMS to customers, and automatically creates corresponding events in Google Calendar.

## Features

- Uses the provided `template` file with `$NAME`, `$TIME`, `$DATE`, and `$DURATION` variables
- Interactive prompts for all reservation details (name, phone, date, time, duration)
- Renders a professional confirmation SMS
- Sends real SMS using Twilio (works for any mobile number)
- Creates Google Calendar event with title format `Appt: $NAME`
- Event includes full confirmation text in description, correct start/end times (America/New_York timezone), and spa location
- `--dry-run` mode to preview the message without sending anything
- Supports `.env` configuration for secrets

## Template

The message template lives in the `template` file next to the script:

```
Hi $NAME, thank you for choosing SoCo Spa! Here is your reservation confirmation for $TIME on $DATE for a $DURATION massage. 

Our location is: 115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585. We are looking forward to seeing you!
```

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Twilio (required for SMS)

1. Sign up at https://www.twilio.com (free trial works)
2. Get your Account SID, Auth Token, and a Twilio phone number (trial numbers can send to verified numbers)
3. Copy `.env.example` to `.env` and fill in the Twilio values:

```bash
cp .env.example .env
# edit .env
```

### 3. Configure Google Calendar (required for events)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Google Calendar API**
4. Go to **APIs & Services > Credentials**
5. Create **OAuth 2.0 Client ID** → Application type: **Desktop app**
6. Download the JSON file and save it as `credentials.json` in this directory

   **Do not commit `credentials.json` or `.env` to git.**

7. First run of the script will open a browser window for OAuth consent. Approve access to your Google Calendar.

### 4. Run the program

```bash
# Interactive mode
python spa_reservation.py

# Preview only (no SMS, no calendar write)
python spa_reservation.py --dry-run
```

During the run you will be prompted for:

- Customer name
- Phone number (must be in E.164 format, e.g. `+18435551212`)
- Appointment date (`YYYY-MM-DD`)
- Appointment time (24-hour `HH:MM`)
- Duration in minutes

After crafting the message you will see a preview and confirmation prompt before anything is sent or created.

## Example Session (Dry Run)

```
SoCo Spa Reservation Confirmation
========================================
Customer name: Maria Lopez
Phone number in E.164 format (e.g. +18435551212): +18435559876
Appointment date (YYYY-MM-DD): 2025-04-15
Appointment time in 24-hour format (HH:MM, e.g. 14:30): 15:00
Duration in minutes (e.g. 60): 90

Crafted confirmation message:
--------------------------------------------------
Hi Maria Lopez, thank you for choosing SoCo Spa! Here is your reservation confirmation for 3:00 PM on April 15, 2025 for a 90-minute massage. 

Our location is: 115 Willbrook Blvd., Suite E, Pawleys Island, SC 29585. We are looking forward to seeing you!
--------------------------------------------------

Will send to: +18435559876
Calendar event title: Appt: Maria Lopez
Time: 3:00 PM on April 15, 2025 (90 minutes)

[DRY RUN] No SMS sent. No calendar event created.
```

## Calendar Event

Created events have:

- **Title**: `Appt: Maria Lopez`
- **Location**: Spa address (from template)
- **Description**: Full confirmation message text
- **Time**: Correct start/end in America/New_York timezone
- **Source**: Your primary calendar (configurable via `GOOGLE_CALENDAR_ID`)

## Environment Variables

All can be set in `.env` or the shell environment:

| Variable                    | Required | Default            | Description |
|-----------------------------|----------|--------------------|-------------|
| `TWILIO_ACCOUNT_SID`        | Yes (for SMS) | - | From Twilio console |
| `TWILIO_AUTH_TOKEN`         | Yes (for SMS) | - | From Twilio console |
| `TWILIO_FROM_PHONE`         | Yes (for SMS) | - | Your Twilio number in E.164 |
| `GOOGLE_CREDENTIALS_FILE`   | No  | `credentials.json` | Path to OAuth client secrets |
| `GOOGLE_TOKEN_FILE`         | No  | `token.json`       | Where to store user token after first auth |
| `GOOGLE_CALENDAR_ID`        | No  | `primary`          | Calendar to write events to |

## Security Notes

- Never commit `.env`, `credentials.json`, or `token.json`
- The `.gitignore` already covers these files
- OAuth token is stored locally after first successful login

## Troubleshooting

- **"Missing Twilio credentials"**: Make sure `.env` is loaded or env vars are exported.
- **Google auth errors**: Delete `token.json` and re-run to force fresh consent.
- **Time shows wrong**: Input uses 24-hour time; output is rendered in America/New_York.
- **SMS not received on trial**: You must verify the destination number in the Twilio console first.

## Files

- `spa_reservation.py` — Main CLI tool
- `template` — Message template (edit as needed)
- `requirements.txt` — Python dependencies
- `.env.example` — Template for secrets

## License

Internal tool for SoCo Spa.
