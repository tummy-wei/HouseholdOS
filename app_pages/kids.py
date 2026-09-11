from __future__ import annotations

from datetime import timedelta

import streamlit as st

from householdos.domain.schedule import EventCategory, ScheduleException
from householdos.ui.runtime import event_time, get_runtime


runtime = get_runtime()
kids_categories = {EventCategory.SCHOOL, EventCategory.SOCCER, EventCategory.ACTIVITY}
kids_events = [
    event
    for day in runtime.analysis.days
    for event in day.events
    if event.category in kids_categories
]
kids_transport = [
    need
    for need in runtime.analysis.transportation
    if any(event.id == need.event_id for event in kids_events)
]
kids_event_ids = {event.id for event in kids_events}

st.title("Kids activity planning")
st.caption("Review school and activities, resolve conflicts, and assign this week's drivers")

metrics = st.columns(3)
metrics[0].metric("Activities", len(kids_events), border=True)
metrics[1].metric(
    "Conflicts",
    sum(
        bool(kids_event_ids.intersection(conflict.event_ids))
        for conflict in runtime.analysis.conflicts
    ),
    border=True,
)
metrics[2].metric(
    "Drivers needed", sum(not item.resolved for item in kids_transport), border=True
)

left, right = st.columns([1.7, 1], gap="large")
with left:
    st.subheader("This week")
    if not kids_events:
        st.info("No kids activities are loaded for this week.")
    for event in kids_events:
        with st.container(border=True):
            st.markdown(
                f"**{event.start_at.strftime('%A, %b %-d')} · {event_time(event)}**"
            )
            st.write(f"{event.person} · {event.title}")
            st.caption(f"{event.location or 'Location pending'} · Source: {event.source_id}")
with right:
    st.subheader("Transportation")
    for need in kids_transport:
        state = "Resolved" if need.resolved else "Needs driver"
        with st.container(border=True):
            st.markdown(f"**{need.person} · {need.event_title}**")
            st.write(f"Driver: {need.driver}")
            st.caption(state)

st.subheader("Change one occurrence")
st.caption("Adjust a recurring activity for the selected week without changing its default schedule.")
labels = {
    f"{item.person} · {item.title} · {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][item.weekday]}": item
    for item in runtime.activities
}
with st.form("kids-weekly-override"):
    selected = st.selectbox("Activity", list(labels))
    activity = labels[selected]
    event_date = st.date_input(
        "Date", value=runtime.week_start + timedelta(days=activity.weekday)
    )
    cancelled = st.checkbox("Cancel this occurrence")
    driver = st.selectbox(
        "Driver", ["Assign weekly", "Parent A", "Parent B", "Carpool"], accept_new_options=True
    )
    change_time = st.checkbox("Change time")
    time_cols = st.columns(2)
    new_start = time_cols[0].time_input(
        "New start", value=activity.start_time, disabled=not change_time
    )
    new_end = time_cols[1].time_input(
        "New end", value=activity.end_time, disabled=not change_time
    )
    note = st.text_input("Note")
    queue_update = st.checkbox("Queue calendar update for approval")
    save = st.form_submit_button("Save weekly change", icon=":material/save:", type="primary")

if save:
    exception = ScheduleException(
        activity_id=activity.activity_id,
        event_date=event_date,
        cancelled=cancelled,
        new_start_time=new_start if change_time else None,
        new_end_time=new_end if change_time else None,
        driver=driver,
        note=note.strip(),
    )
    runtime.repository.save_schedule_exception(exception)
    if queue_update:
        runtime.repository.propose_external_action(
            "calendar.update",
            "Update one kids activity occurrence",
            f"{activity.person}: {activity.title} on {event_date.isoformat()}",
            exception.model_dump(mode="json"),
        )
    st.toast("Kids activity change saved", icon=":material/check_circle:")
    st.rerun()
