from __future__ import annotations

from datetime import timedelta

import streamlit as st

from householdos.domain.operations import (
    NewHouseholdTask,
    TaskPriority,
    TaskScope,
    TaskStatus,
)
from householdos.ui.runtime import get_runtime


runtime = get_runtime()
repository = runtime.repository

st.title("Parent and church tasks")
st.caption("One reviewable list for household coordination and ministry preparation")

with st.expander("Add a task", icon=":material/add_task:"):
    with st.form("add-task"):
        title = st.text_input("Task", placeholder="Confirm Friday fellowship activity")
        scope = st.segmented_control(
            "Scope", [item.value for item in TaskScope], default=TaskScope.PARENTS.value
        )
        col1, col2, col3 = st.columns(3)
        owner = col1.selectbox(
            "Owner", ["Unassigned", "Kang", "Jessie"], accept_new_options=True
        )
        priority = col2.selectbox("Priority", [item.value for item in TaskPriority])
        has_due_date = col3.checkbox("Set due date", value=True)
        due_date = st.date_input("Due date", value=runtime.week_start) if has_due_date else None
        notes = st.text_area("Notes", height=80)
        submitted = st.form_submit_button("Add task", icon=":material/add:", type="primary")
    if submitted and title.strip():
        repository.create_task(
            NewHouseholdTask(
                title=title.strip(),
                scope=TaskScope(scope),
                owner=owner,
                due_date=due_date,
                priority=TaskPriority(priority),
                notes=notes.strip(),
            )
        )
        st.toast("Task added", icon=":material/check_circle:")
        st.rerun()

with st.container(horizontal=True, vertical_alignment="center"):
    if st.button("Add weekly ministry tasks", icon=":material/event_repeat:"):
        templates = [
            NewHouseholdTask(
                title="Review and send Friday fellowship reminder",
                scope=TaskScope.CHURCH,
                owner="Kang",
                due_date=runtime.week_start + timedelta(days=2),
                priority=TaskPriority.HIGH,
                source="Weekly ministry workflow",
            ),
            NewHouseholdTask(
                title="Confirm Bible study leader, helpers, and materials",
                scope=TaskScope.CHURCH,
                owner="Kang",
                due_date=runtime.week_start + timedelta(days=2),
                priority=TaskPriority.HIGH,
                source="Weekly ministry workflow",
                notes="Preparation reminder should be sent about 1.5 weeks before formal study.",
            ),
            NewHouseholdTask(
                title="Extract and review Saturday online prayer announcement",
                scope=TaskScope.CHURCH,
                owner="Kang",
                due_date=runtime.week_start + timedelta(days=5),
                priority=TaskPriority.HIGH,
                source="Weekly ministry workflow",
                notes="Use the current pastor email or verified WeChat source. Target: Saturday 7:30 AM.",
            ),
            NewHouseholdTask(
                title="Extract and review Sunday message forecast",
                scope=TaskScope.CHURCH,
                owner="Kang",
                due_date=runtime.week_start + timedelta(days=5),
                priority=TaskPriority.HIGH,
                source="Weekly ministry workflow",
                notes="Confirm the forecast is current before approving the LINE post.",
            ),
            NewHouseholdTask(
                title="Index this week's Bible study materials",
                scope=TaskScope.CHURCH,
                owner="Kang",
                due_date=runtime.week_start + timedelta(days=2),
                priority=TaskPriority.MEDIUM,
                source="Weekly ministry workflow",
                notes="Use stable S&L Drive links and mark the material review state.",
            ),
        ]
        existing = {task.title for task in repository.list_tasks()}
        for task in templates:
            if task.title not in existing:
                repository.create_task(task)
        st.toast("Weekly ministry tasks added", icon=":material/check_circle:")
        st.rerun()

    scope_filter = st.selectbox(
        "Filter tasks", ["Open", *[item.value for item in TaskScope], "All"]
    )

tasks = repository.list_tasks(include_done=scope_filter == "All")
if scope_filter in {item.value for item in TaskScope}:
    tasks = [task for task in tasks if task.scope.value == scope_filter]

if not tasks:
    st.info("No tasks in this view. Add one above or load the weekly ministry tasks.")

for task in tasks:
    with st.container(border=True):
        row = st.container(horizontal=True, vertical_alignment="center")
        row.markdown(f"**{task.title}**")
        row.badge(task.scope.value, color="blue" if task.scope is TaskScope.CHURCH else "gray")
        row.badge(task.priority.value, color="red" if task.priority is TaskPriority.HIGH else "orange")
        due = task.due_date.strftime("%a, %b %-d") if task.due_date else "No due date"
        st.caption(f"Owner: {task.owner} · Due: {due} · Source: {task.source}")
        if task.notes:
            st.write(task.notes)
        with st.container(horizontal=True):
            if task.status is not TaskStatus.IN_PROGRESS and task.status is not TaskStatus.DONE:
                if st.button("Start", key=f"start-{task.id}", icon=":material/play_arrow:"):
                    repository.update_task_status(task.id, TaskStatus.IN_PROGRESS)
                    st.rerun()
            if task.status is not TaskStatus.DONE:
                if st.button("Mark done", key=f"done-{task.id}", icon=":material/check:"):
                    repository.update_task_status(task.id, TaskStatus.DONE)
                    st.rerun()
            else:
                st.badge("Done", icon=":material/check_circle:", color="green")
