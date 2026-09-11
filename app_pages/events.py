from __future__ import annotations

import streamlit as st

from householdos.ui.runtime import event_time, get_runtime
from householdos.workflows.operations import (
    build_event_line_announcement,
    build_event_one_pager,
)


runtime = get_runtime()
events = [event for day in runtime.analysis.days for event in day.events]

st.title("Event briefs")
st.caption("Turn any calendar event into a one-page operating brief and announcement draft")

timed_events = [event for event in events if not event.all_day]
event_options = {
    f"{event.start_at.strftime('%a %-m/%-d %-I:%M %p')} · {event.person} · {event.title}": event
    for event in timed_events
}
selected_label = st.selectbox("Choose an event", list(event_options))
event = event_options[selected_label]
one_pager = build_event_one_pager(event, runtime.analysis)

summary_col, action_col = st.columns([1.5, 1], gap="large")
with summary_col:
    with st.container(border=True):
        st.subheader(event.title)
        st.markdown(f"**{event.start_at.strftime('%A, %B %-d')} · {event_time(event)}**")
        st.write(f"{event.person} · {event.category.value}")
        st.write(event.location or "Location to be confirmed")
        st.caption(f"Source: {event.source_id}")
with action_col:
    st.download_button(
        "Download one-pager",
        data=one_pager.markdown,
        file_name=one_pager.filename,
        mime="text/markdown",
        icon=":material/download:",
        type="primary",
        width="stretch",
    )
    st.caption("Generated locally from normalized calendar data.")

preview_tab, announcement_tab = st.tabs(["One-pager preview", "Announcement draft"])
with preview_tab:
    st.markdown(one_pager.markdown)
with announcement_tab:
    announcement = build_event_line_announcement(event)
    edited_announcement = st.text_area(
        "Traditional Chinese LINE announcement",
        value=announcement,
        height=240,
        key=f"event-announcement-{event.id}",
    )
    destination = st.selectbox(
        "Destination", ["Bible fellowship LINE group", "Helpers LINE group", "Family chat"]
    )
    if st.button("Queue for approval", icon=":material/approval:", type="primary"):
        runtime.repository.propose_external_action(
            tool_name="line.send",
            action="Send event announcement",
            target=destination,
            payload={"event_id": event.id, "message": edited_announcement},
        )
        st.toast("Announcement queued for approval", icon=":material/check_circle:")

