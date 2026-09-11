from __future__ import annotations

import streamlit as st

from householdos.domain.operations import TaskScope
from householdos.domain.schedule import EventCategory
from householdos.ui.runtime import event_time, get_runtime


runtime = get_runtime()
analysis = runtime.analysis
tasks = runtime.repository.list_tasks(include_done=False)
events = [event for day in analysis.days for event in day.events]
kids_events = [
    event
    for event in events
    if event.category in {EventCategory.SCHOOL, EventCategory.SOCCER, EventCategory.ACTIVITY}
]
open_drivers = sum(not item.resolved for item in analysis.transportation)
pending_approvals = sum(
    item.status == "Proposed" for item in runtime.repository.list_approval_requests()
)
grocery_items = runtime.repository.list_grocery_items(
    runtime.week_start, include_purchased=False
)
travel_plans = runtime.repository.list_travel_plans()
church_tasks = [task for task in tasks if task.scope is TaskScope.CHURCH]
maintenance_tasks = [task for task in tasks if task.scope is TaskScope.MAINTENANCE]

st.title("Good week, let’s make it workable")
st.caption(
    f"Command center for {analysis.week_start.strftime('%B %-d')}–{analysis.week_end.strftime('%B %-d, %Y')}"
)

metric_cols = st.columns(4)
metric_cols[0].metric("Calendar events", len(events), border=True)
metric_cols[1].metric("Schedule conflicts", len(analysis.conflicts), border=True)
metric_cols[2].metric("Open drivers", open_drivers, border=True)
metric_cols[3].metric("Open tasks", len(tasks), border=True)

st.subheader("Five-domain readiness")
st.dataframe(
    [
        {
            "Domain": "Kids activities",
            "This week": f"{len(kids_events)} activities; {open_drivers} drivers open",
            "Next action": "Resolve conflicts and weekly drivers" if open_drivers else "Review schedule changes",
        },
        {
            "Domain": "Church events",
            "This week": f"{len(church_tasks)} open preparation tasks",
            "Next action": "Prepare reminder, study team, and pastor message",
        },
        {
            "Domain": "Groceries",
            "This week": f"{len(grocery_items)} items still needed",
            "Next action": "Confirm meals and shopping owner",
        },
        {
            "Domain": "Travel",
            "This week": f"{len(travel_plans)} active trip plans",
            "Next action": "Confirm dates, lodging, and references" if travel_plans else "No active trip",
        },
        {
            "Domain": "House maintenance",
            "This week": f"{len(maintenance_tasks)} open tasks",
            "Next action": "Assign owner and due date" if maintenance_tasks else "No maintenance due",
        },
    ],
    hide_index=True,
    width="stretch",
)

left, right = st.columns([1.7, 1], gap="large")
with left:
    st.subheader("This week")
    for day in analysis.days:
        timed = [event for event in day.events if not event.all_day]
        all_day = [event for event in day.events if event.all_day]
        with st.container(border=True):
            header = st.container(horizontal=True, vertical_alignment="center")
            header.markdown(f"**{day.date.strftime('%A')}**")
            header.caption(day.date.strftime("%B %-d"))
            if all_day:
                st.caption(" · ".join(event.title for event in all_day[:3]))
            if not timed:
                st.write("No timed events")
            for event in timed:
                st.markdown(
                    f"**{event_time(event)}**  {event.person} · {event.title}"
                    + (f"  \n{event.location}" if event.location else "")
                )

with right:
    st.subheader("Needs attention")
    if analysis.conflicts:
        for conflict in analysis.conflicts:
            st.error(conflict.message, icon=":material/event_busy:")
    else:
        st.success("No same-person overlaps", icon=":material/check_circle:")
    if open_drivers:
        st.warning(
            f"{open_drivers} driver assignments are still open.",
            icon=":material/directions_car:",
        )
    if pending_approvals:
        st.info(
            f"{pending_approvals} external action(s) await review.",
            icon=":material/approval:",
        )

    st.subheader("Priority tasks")
    if not tasks:
        st.caption("No tasks yet. Add weekly parent and church tasks on the Tasks page.")
    for task in tasks[:6]:
        with st.container(border=True):
            st.markdown(f"**{task.title}**")
            due = task.due_date.strftime("%a, %b %-d") if task.due_date else "No due date"
            st.caption(f"{task.scope.value} · {task.owner} · {due}")

    st.subheader("System readiness")
    st.markdown(
        ":green-badge[Calendars loaded] "
        ":green-badge[Local changes enabled] "
        + (":green-badge[AI ready]" if runtime.settings.has_api_key else ":orange-badge[AI key needed]")
    )
    st.caption("Gmail and LINE delivery adapters are not connected yet.")
