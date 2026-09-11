from __future__ import annotations

from datetime import timedelta

import streamlit as st

from householdos.domain.schedule import ScheduleException
from householdos.ui.runtime import get_runtime, load_activities


runtime = get_runtime()

st.title("Sources and settings")
st.caption("Inspect source authority, recurring data, and one-week calendar overrides")

source_cols = st.columns(3)
with source_cols[0].container(border=True, height="stretch"):
    st.markdown("#### :material/school: School calendars")
    st.write("Student A and Student B school calendar snapshots")
    st.badge("Read only", color="green")
with source_cols[1].container(border=True, height="stretch"):
    st.markdown("#### :material/sports_soccer: Soccer calendars")
    st.write("Student A and Student B sports calendar snapshots")
    st.badge("Read only", color="green")
with source_cols[2].container(border=True, height="stretch"):
    st.markdown("#### :material/church: Church calendars")
    st.write("Public and Helpers calendars are maintained by the existing Apps Script sync")
    st.badge("Adapter pending", color="orange")

st.subheader("Source contribution this week")
st.dataframe(
    [
        {"Source": source, "Events": count, "Access": "Read only"}
        for source, count in sorted(runtime.analysis.source_event_counts.items())
    ],
    hide_index=True,
    width="stretch",
)

with st.container(horizontal=True, vertical_alignment="center"):
    if st.button("Reload local source files", icon=":material/refresh:"):
        load_activities.clear()
        st.rerun()
    st.caption("ICS files and recurring activity JSON are local snapshots.")

st.subheader("Recurring activities")
st.dataframe(
    [
        {
            "Person": item.person,
            "Activity": item.title,
            "Day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][item.weekday],
            "Start": item.start_time.strftime("%-I:%M %p"),
            "End": item.end_time.strftime("%-I:%M %p"),
            "Location": item.location,
            "Arrival buffer": item.arrival_buffer_min,
            "Driver": item.driver,
        }
        for item in runtime.activities
    ],
    hide_index=True,
    width="stretch",
    column_config={
        "Location": st.column_config.TextColumn(width="large"),
        "Arrival buffer": st.column_config.NumberColumn(format="%d min"),
    },
)

st.subheader("Add a one-week change")
st.caption("Use this for a cancellation, substitute driver, or one-time time/location change.")
day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
labels = {
    f"{item.person} · {item.title} · {day_names[item.weekday]}": item
    for item in runtime.activities
}
with st.form("schedule-exception"):
    selected_label = st.selectbox("Recurring activity", list(labels))
    activity = labels[selected_label]
    default_date = runtime.week_start + timedelta(days=activity.weekday)
    event_date = st.date_input("Date", value=default_date)
    cancelled = st.checkbox("Cancel this occurrence")
    change_time = st.checkbox("Change time")
    time_cols = st.columns(2)
    new_start = time_cols[0].time_input(
        "New start", value=activity.start_time, disabled=not change_time
    )
    new_end = time_cols[1].time_input(
        "New end", value=activity.end_time, disabled=not change_time
    )
    change_location = st.checkbox("Change location")
    new_location = st.text_input(
        "New location", value=activity.location, disabled=not change_location
    )
    driver = st.selectbox(
        "Driver", ["Assign weekly", "Parent A", "Parent B", "Carpool"], accept_new_options=True
    )
    note = st.text_input("Reason or note")
    queue_external = st.checkbox("Queue a matching calendar update for approval")
    submitted = st.form_submit_button("Save weekly change", icon=":material/save:", type="primary")
if submitted:
    exception = ScheduleException(
        activity_id=activity.activity_id,
        event_date=event_date,
        cancelled=cancelled,
        new_start_time=new_start if change_time else None,
        new_end_time=new_end if change_time else None,
        new_location=new_location if change_location else None,
        driver=driver,
        note=note.strip(),
    )
    runtime.repository.save_schedule_exception(exception)
    if queue_external:
        runtime.repository.propose_external_action(
            tool_name="calendar.update",
            action="Update one calendar occurrence",
            target=f"{activity.person}: {activity.title} on {event_date.isoformat()}",
            payload=exception.model_dump(mode="json"),
        )
    st.toast("Weekly change saved", icon=":material/check_circle:")
    st.rerun()

saved = runtime.repository.list_schedule_exceptions(
    runtime.week_start, runtime.week_start + timedelta(days=6)
)
if saved:
    st.subheader("Saved changes for this week")
    st.dataframe(
        [
            {
                "Date": item.event_date,
                "Activity": item.activity_id,
                "Cancelled": item.cancelled,
                "Driver": item.driver or "",
                "New location": item.new_location or "",
                "Note": item.note,
            }
            for item in saved
        ],
        hide_index=True,
        width="stretch",
    )

st.subheader("Agent configuration")
with st.container(border=True):
    st.write(f"Model: `{runtime.settings.openai_model}`")
    if runtime.settings.has_api_key:
        st.success("OpenAI API key is available.", icon=":material/check_circle:")
    else:
        st.warning(
            "OPENAI_API_KEY is not set. Chat still answers common schedule and task queries offline.",
            icon=":material/key:",
        )
    st.caption("No credentials are displayed or stored in the UI.")

st.subheader("Confirmed household memory")
st.caption("Only preferences explicitly saved here become durable planning memory.")
with st.form("confirmed-preference"):
    pref_key = st.text_input("Preference key", placeholder="dietary.student_b")
    pref_value = st.text_input("Confirmed value", placeholder="No confirmed restriction")
    pref_cols = st.columns(3)
    pref_owner = pref_cols[0].selectbox(
        "Owner", ["Household", "Parent A", "Parent B", "Student A", "Student B"]
    )
    pref_effective = pref_cols[1].date_input("Effective date", value=runtime.week_start)
    pref_sensitivity = pref_cols[2].selectbox(
        "Sensitivity", ["Household", "Church admin", "Public"]
    )
    save_preference = st.form_submit_button(
        "Confirm and save", icon=":material/save:", type="primary"
    )
if save_preference:
    if not pref_key.strip() or not pref_value.strip():
        st.warning("Preference key and value are required.")
    else:
        runtime.repository.upsert_preference(
            pref_key.strip(),
            pref_value.strip(),
            pref_owner,
            "Explicit UI confirmation",
            pref_effective,
            pref_sensitivity,
        )
        st.toast("Confirmed preference saved", icon=":material/check_circle:")
        st.rerun()

preferences = runtime.repository.list_preferences()
if preferences:
    st.dataframe(
        [
            {
                "Key": item.key,
                "Value": item.value,
                "Owner": item.owner,
                "Effective": item.effective_date,
                "Sensitivity": item.sensitivity,
                "Source": item.source,
            }
            for item in preferences
        ],
        hide_index=True,
        width="stretch",
    )
