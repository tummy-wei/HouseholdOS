from __future__ import annotations

from datetime import timedelta

import streamlit as st

from householdos.domain.operations import NewHouseholdTask, TaskPriority, TaskScope, TaskStatus
from householdos.ui.runtime import get_runtime


runtime = get_runtime()
repository = runtime.repository
tasks = [
    task
    for task in repository.list_tasks(include_done=True)
    if task.scope is TaskScope.MAINTENANCE
]

st.title("House maintenance")
st.caption("Capture repairs, recurring care, seasonal work, and service appointments")

metrics = st.columns(3)
metrics[0].metric("Open", sum(task.status is not TaskStatus.DONE for task in tasks), border=True)
metrics[1].metric("High priority", sum(task.priority is TaskPriority.HIGH and task.status is not TaskStatus.DONE for task in tasks), border=True)
metrics[2].metric("Completed", sum(task.status is TaskStatus.DONE for task in tasks), border=True)

with st.expander("Add maintenance task", icon=":material/home_repair_service:"):
    with st.form("add-maintenance"):
        title = st.text_input("Task", placeholder="Replace furnace filter")
        cols = st.columns(3)
        owner = cols[0].selectbox("Owner", ["Unassigned", "Parent A", "Parent B"], accept_new_options=True)
        priority = cols[1].selectbox("Priority", [item.value for item in TaskPriority])
        due = cols[2].date_input("Due", value=runtime.week_start + timedelta(days=6))
        notes = st.text_area("Service details or recurrence", height=90)
        add = st.form_submit_button("Add maintenance task", icon=":material/add:", type="primary")
    if add:
        if not title.strip():
            st.warning("Enter a maintenance task.")
        else:
            repository.create_task(
                NewHouseholdTask(
                    title=title.strip(), scope=TaskScope.MAINTENANCE, owner=owner,
                    due_date=due, priority=TaskPriority(priority),
                    source="Maintenance planner", notes=notes.strip(),
                )
            )
            st.toast("Maintenance task added", icon=":material/check_circle:")
            st.rerun()

show_completed = st.toggle("Show completed", value=False)
visible = tasks if show_completed else [task for task in tasks if task.status is not TaskStatus.DONE]
if not visible:
    st.info("No maintenance tasks in this view.")
for task in visible:
    with st.container(border=True):
        row = st.container(horizontal=True, vertical_alignment="center")
        row.markdown(f"**{task.title}**")
        row.badge(task.priority.value, color="red" if task.priority is TaskPriority.HIGH else "orange")
        st.caption(f"Owner: {task.owner} · Due: {task.due_date or 'No date'}")
        if task.notes:
            st.write(task.notes)
        if task.status is not TaskStatus.DONE and st.button(
            "Mark done", key=f"maintenance-{task.id}", icon=":material/check:"
        ):
            repository.update_task_status(task.id, TaskStatus.DONE)
            st.rerun()
