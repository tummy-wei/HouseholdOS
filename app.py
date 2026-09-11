"""HouseholdOS Streamlit entry point."""

from datetime import date, timedelta

import streamlit as st

from householdos.ui.runtime import REPOSITORY_CACHE_VERSION, get_repository
from householdos.config import Settings


st.set_page_config(
    page_title="HouseholdOS",
    page_icon=":material/home:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault(
    "household_week_start", date.today() - timedelta(days=date.today().weekday())
)
st.session_state.setdefault("household_chat_messages", [])
st.session_state.setdefault("pastor_line_draft", "")

settings = Settings.from_env()
repository = get_repository(
    str(settings.database_path), REPOSITORY_CACHE_VERSION
)

with st.sidebar:
    st.markdown("## :material/home: HouseholdOS")
    st.caption("Family and ministry operations")
    selected_week = st.date_input(
        "Planning week",
        value=st.session_state.household_week_start,
        key="global_week_picker",
    )
    st.session_state.household_week_start = selected_week - timedelta(
        days=selected_week.weekday()
    )
    open_tasks = len(repository.list_tasks(include_done=False))
    proposed = sum(
        item.status == "Proposed" for item in repository.list_approval_requests()
    )
    st.metric("Open tasks", open_tasks, border=True)
    st.metric("Awaiting approval", proposed, border=True)
    st.caption("Local-first · external writes require approval")

page = st.navigation(
    {
        "Plan": [
            st.Page("app_pages/home.py", title="Command center", icon=":material/space_dashboard:"),
            st.Page("app_pages/calendar.py", title="All events", icon=":material/calendar_month:"),
            st.Page("app_pages/weekly_brief.py", title="Weekly brief", icon=":material/view_week:"),
            st.Page("app_pages/kids.py", title="Kids activities", icon=":material/school:"),
            st.Page("app_pages/ministry.py", title="Church planning", icon=":material/church:"),
            st.Page("app_pages/groceries.py", title="Groceries", icon=":material/shopping_cart:"),
            st.Page("app_pages/travel.py", title="Travel", icon=":material/luggage:"),
            st.Page("app_pages/maintenance.py", title="House maintenance", icon=":material/home_repair_service:"),
        ],
        "Work": [
            st.Page("app_pages/assistant.py", title="Ask HouseholdOS", icon=":material/chat:"),
            st.Page("app_pages/tasks.py", title="Tasks", icon=":material/checklist:"),
            st.Page("app_pages/events.py", title="Event briefs", icon=":material/event_note:"),
        ],
        "Review": [
            st.Page("app_pages/approvals.py", title="Approvals", icon=":material/approval:"),
            st.Page("app_pages/trace_evaluation.py", title="Trace and evaluation", icon=":material/monitoring:"),
            st.Page("app_pages/sources.py", title="Sources and settings", icon=":material/database:"),
        ],
    },
    position="sidebar",
)

page.run()
