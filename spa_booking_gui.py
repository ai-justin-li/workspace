"""
SoCo Spa - Booking GUI (Streamlit)

A simple graphical interface for the two receptionists.

Run with:
    streamlit run spa_booking_gui.py
"""

import streamlit as st
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

from pathlib import Path
from string import Template

from spa_reservation import (
    load_therapists,
    build_confirmation_details,
    build_event_summary,
    get_color_name,
    analyze_booking_conflicts,
    create_calendar_event,
)

TEMPLATE_PATH = Path(__file__).parent / "template"

st.set_page_config(
    page_title="SoCo Spa Booking",
    page_icon="💆‍♀️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Mobile-friendly styling + PWA hints
st.markdown("""
<style>
    /* Prevent iOS auto-zoom on input focus */
    .stTextInput input, .stNumberInput input, .stSelectbox, .stTextArea textarea {
        font-size: 16px !important;
    }
    
    /* Larger touch targets */
    .stButton button {
        min-height: 48px !important;
        font-size: 16px !important;
    }
    
    /* Make the app feel more native on phone */
    .block-container {
        padding-top: 0.5rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        max-width: 100% !important;
    }
    
    /* Cleaner look on mobile */
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

st.title("SoCo Spa — Booking")
st.caption("Receptionist tool • Built for iPhone use")

st.info("**Tip for receptionists:** Add this page to your iPhone Home Screen (Safari → Share → Add to Home Screen) so it feels like a real app you can open while on a call.")

# Add PWA manifest so it can be installed on iPhone home screen
st.markdown("""
<link rel="manifest" href="data:application/manifest+json,{
  \"name\": \"SoCo Spa Booking\",
  \"short_name\": \"SoCo Booking\",
  \"start_url\": \".\",
  \"display\": \"standalone\",
  \"background_color\": \"#ffffff\",
  \"theme_color\": \"#0f766e\",
  \"icons\": [{
    \"src\": \"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%92%86%E2%80%8D%E2%99%80%EF%B8%8F%3C/text%3E%3C/svg%3E\",
    \"sizes\": \"192x192\",
    \"type\": \"image/svg+xml\"
  }]
}">
""", unsafe_allow_html=True)

# --- Smart Defaults ---
today_str = date.today().strftime("%Y%m%d")

# Calculate nearest next half hour
now = datetime.now()
minutes = now.minute
if minutes < 30:
    next_time = now.replace(minute=30, second=0, microsecond=0)
else:
    next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
default_time_str = next_time.strftime("%H%M")

# --- Quick Availability View (always visible, mobile friendly) ---
st.subheader("📅 Next 5 Hours")

col1, col2 = st.columns([3, 1])
with col1:
    st.caption("Current bookings on the calendar")
with col2:
    if st.button("Refresh", use_container_width=True):
        st.rerun()

try:
    from spa_reservation import get_calendar_service
    service = get_calendar_service()

    now = datetime.now(ZoneInfo("America/New_York"))
    time_max = now + timedelta(hours=12)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        st.success("✅ No appointments in the next 12 hours — you're clear!")
    else:
        for event in events:
            summary = event.get('summary', 'Untitled')
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(ZoneInfo("America/New_York"))
                time_str = start_dt.strftime("%-I:%M %p")
            else:
                time_str = start
            st.write(f"**{time_str}** — {summary}")

except Exception as e:
    st.warning("Could not load live calendar (check credentials).")
    st.caption("You can still create bookings — just double-check the calendar manually.")

st.divider()

# Load therapists once
therapists = load_therapists()
therapist_names = [t["name"] for t in therapists]

# --- Form ---
with st.form("booking_form"):
    st.subheader("New Reservation")

    name = st.text_input("Customer Name *", placeholder="Customer name")

    col1, col2 = st.columns([1, 1])
    with col1:
        num_massages = st.number_input("Number of Massages", min_value=1, max_value=6, value=1, step=1)
    with col2:
        is_couples = st.checkbox("This is a Couples Massage", value=False)

    massage_type = st.text_input("Massage Type (optional)", placeholder="deep tissue, Swedish, hot stone...")

    # Therapist
    therapist_options = ["No specific therapist"] + therapist_names
    selected_therapist = st.selectbox("Requested Therapist", therapist_options, index=0)
    therapist_name = selected_therapist if selected_therapist != "No specific therapist" else ""

    # Date & Time - stacked on phone for easier tapping
    st.markdown("**Date & Time**")
    date_str = st.text_input("Date (YYYYMMDD)", value=today_str)
    time_str = st.text_input("Time (HHMM)", value=default_time_str)

    duration = st.number_input("Duration (minutes)", min_value=30, max_value=180, value=60, step=15)

    notes = st.text_area("Notes / Special Requests (optional)", 
                         placeholder="Lower back issues, prefers firm pressure...",
                         height=70)

    submitted = st.form_submit_button("Preview & Check Conflicts", type="primary", use_container_width=True)

# --- Preview Section ---
if submitted:
    # Basic validation
    errors = []
    if not name:
        errors.append("Customer name is required.")
    if not date_str or not time_str:
        errors.append("Date and time are required.")

    try:
        appt_date = datetime.strptime(date_str, "%Y%m%d").date()
        appt_time = datetime.strptime(time_str, "%H%M").time()
    except ValueError:
        errors.append("Invalid date or time format. Use YYYYMMDD and HHMM.")

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    tz = ZoneInfo("America/New_York")
    start_dt = datetime.combine(appt_date, appt_time, tzinfo=tz)
    end_dt = start_dt + timedelta(minutes=duration)

    display_date = appt_date.strftime("%B %d, %Y")
    display_time = start_dt.strftime("%-I:%M %p") if hasattr(start_dt, 'strftime') else f"{appt_time.hour}:{appt_time.minute:02d}"
    display_duration = f"{duration}-minute"

    # Build the inner confirmation phrase
    confirmation_details = build_confirmation_details(
        num_massages, is_couples, massage_type, display_duration, therapist_name
    )

    # Build the FULL confirmation message using the template (this is what gets sent via SMS)
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    t = Template(template_text)
    full_message = t.safe_substitute(
        NAME=name,
        TIME=display_time,
        DATE=display_date,
        CONFIRMATION_DETAILS=confirmation_details,
    )

    # Append notes if provided (so the receptionist can copy everything at once)
    if notes.strip():
        full_message += f"\n\nNotes for therapist: {notes.strip()}"

    # Build title and color
    num_massages = int(num_massages)  # ensure int

    event_title = build_event_summary(name, num_massages, notes)

    if num_massages > 1:
        color_id = "10"  # Basil - forced for multi-massage bookings
    elif is_couples:
        color_id = "2"   # Sage
    elif therapist_name:
        therapist_obj = next((t for t in therapists if t["name"] == therapist_name), None)
        color_id = therapist_obj["default_color"] if therapist_obj else "7"
    else:
        color_id = "7"   # Peacock default

    color_name = get_color_name(color_id)

    # Store in session state for later actions
    st.session_state["booking_data"] = {
        "name": name,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "therapist_name": therapist_name,
        "is_couples": is_couples,
        "massage_type": massage_type,
        "num_massages": num_massages,
        "duration": duration,
        "notes": notes.strip(),
        "full_message": full_message,           # This is the complete text to copy-paste for SMS
        "event_title": event_title,
        "color_id": color_id,
        "color_name": color_name,
        "display_time": display_time,
        "display_date": display_date,
    }

    st.success("Preview generated. Running automatic conflict analysis...")

    # Automatically run conflict analysis right after submission
    booking_data = st.session_state["booking_data"]
    with st.spinner("Checking Google Calendar for conflicts..."):
        analysis = analyze_booking_conflicts(
            booking_data["start_dt"],
            booking_data["end_dt"],
            requested_therapist_name=booking_data["therapist_name"] if booking_data["therapist_name"] else None,
            num_massages=booking_data["num_massages"],
            is_couples=booking_data["is_couples"],
        )
        st.session_state["conflict_analysis"] = analysis

# --- Display Preview + Automatic Conflict Analysis ---
if "booking_data" in st.session_state:
    data = st.session_state["booking_data"]

    st.divider()
    st.subheader("Booking Preview")

    st.markdown(f"**Message that will be sent (copy this for SMS):**")
    st.info(data["full_message"])

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Calendar Title:**\n`{data['event_title']}`")
        st.markdown(f"**Therapist:** {data['therapist_name'] or 'Any / Not specified'}")
    with col_b:
        st.markdown(f"**Time:** {data['display_time']} on {data['display_date']}")
        st.markdown(f"**Color:** {data['color_name']} (ID {data['color_id']})")

    # Show automatic conflict analysis results
    if "conflict_analysis" in st.session_state:
        analysis = st.session_state["conflict_analysis"]

        st.divider()
        st.subheader("Conflict Analysis (Automatic)")

        if analysis["hard_conflict"]:
            st.error("⚠️ **Hard Conflict Detected** — Booking should not proceed without review.")

            if analysis["capacity_violation"]:
                slots = analysis.get('booking_slots', 1)
                current_used = analysis.get('current_slots_used', analysis.get('current_concurrent', 0))
                st.warning(
                    f"**Capacity Violation**: This booking would use **{slots}** therapist slots. "
                    f"Current load: {current_used}/{analysis['max_capacity']}."
                )

            if analysis["therapist_conflict"]:
                st.error(f"**Therapist Conflict**: {analysis['conflicting_therapist']} already has an appointment overlapping this time.")

        elif analysis["conflicts"]:
            st.info("ℹ️ Other appointments overlap this time slot, but they are with different therapists. This is acceptable.")
            st.write("**Overlapping appointments:**")
            for c in analysis["conflicts"]:
                st.write(f"- {c['summary']} — {c['start']}")

        else:
            st.success("✅ No conflicts. Time slot is clear.")

    # Final Create Button
    st.divider()
    create_clicked = st.button("Create Booking in Google Calendar", type="primary")

    if create_clicked:
        with st.spinner("Creating calendar event..."):
            try:
                # Create exactly one event (title will show quantity if > 1, e.g. "Appt x3: John")
                event = create_calendar_event(
                    name=data["name"],
                    description=f"Customer: {data['name']}\n"
                                f"Therapist: {data['therapist_name'] or 'Unassigned'}\n"
                                f"Notes: {data['notes'] or '-'}",
                    start_dt=data["start_dt"],
                    end_dt=data["end_dt"],
                    therapist=data["therapist_name"],
                    num_massages=data.get("num_massages", 1),
                    notes=data.get("notes", ""),
                    color_id=data["color_id"],
                )

                st.success("Booking created successfully!")
                st.markdown(f"[View in Google Calendar]({event.get('htmlLink')})")
                st.balloons()

                # Clear state
                for key in ["booking_data", "conflict_analysis"]:
                    if key in st.session_state:
                        del st.session_state[key]

            except Exception as e:
                st.error(f"Failed to create booking: {e}")
                st.info("You can still create the event manually in Google Calendar using the details above.")

# --- iPhone Home Screen Instructions ---
st.divider()
with st.expander("📱 Install on your iPhone (makes it feel like a real app)", expanded=False):
    st.markdown("""
    **Best way to use this while on calls:**

    1. On your iPhone, open this page in **Safari**.
    2. Tap the **Share** button (box with arrow pointing up).
    3. Scroll down and tap **"Add to Home Screen"**.
    4. Tap **Add**.

    It will now appear on your home screen like a normal app. You can open it while on a phone call with a customer.

    **To access it from your phone:**
    - If running locally on a Mac: Use **ngrok** (`ngrok http 8501`) and open the https link on your iPhone.
    - Or host it properly so it's always available.
    """)
