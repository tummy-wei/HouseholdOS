from __future__ import annotations

import calendar as month_calendar
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from householdos.infrastructure.external_actions import adapter_readiness, list_sheet_events
from householdos.ui.runtime import calendar_sources, get_runtime
from householdos.workflows.schedule_analysis import ScheduleAnalysisWorkflow


runtime = get_runtime()
readiness = adapter_readiness(runtime.settings)
today = date.today()
LOCAL_TIMEZONE = ZoneInfo("America/Los_Angeles")


def parse_church_date(value: str) -> date | None:
    for date_format in ("%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), date_format).date()
        except ValueError:
            continue
    return None


def parse_church_time(value: str, fallback: time) -> time:
    for time_format in ("%I:%M %p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), time_format).time()
        except ValueError:
            continue
    return fallback


def load_family_events(range_start: date, range_end: date) -> list[dict[str, object]]:
    events_by_id: dict[str, object] = {}
    week_start = range_start - timedelta(days=range_start.weekday())
    workflow = ScheduleAnalysisWorkflow()
    while week_start <= range_end:
        week_end = week_start + timedelta(days=6)
        exceptions = runtime.repository.list_schedule_exceptions(week_start, week_end)
        analysis = workflow.run(week_start, calendar_sources(), runtime.activities, exceptions)
        for day in analysis.days:
            for event in day.events:
                if range_start <= event.start_at.date() <= range_end:
                    events_by_id[event.id] = event
        week_start += timedelta(days=7)
    return [
        {
            "id": event.id,
            "date": event.start_at.date(),
            "start": event.start_at,
            "end": event.end_at,
            "title": event.title,
            "person": event.person,
            "category": event.category.value,
            "source": event.source_id,
            "location": event.location,
            "details": event.description,
            "status": "Active",
            "all_day": event.all_day,
        }
        for event in events_by_id.values()
    ]


def load_church_events() -> list[dict[str, object]]:
    cache = st.session_state.get("church_calendar_events", {})
    public_events = cache.get("26H2-Calendar-Public", [])
    helper_events = cache.get("26H2-Calendar-Helpers", [])
    helpers_by_id = {item.get("event_id"): item for item in helper_events}
    combined_rows = list(public_events)
    public_ids = {item.get("event_id") for item in public_events}
    combined_rows.extend(item for item in helper_events if item.get("event_id") not in public_ids)
    normalized: list[dict[str, object]] = []
    for row in combined_rows:
        event_date = parse_church_date(row.get("date", ""))
        if not event_date:
            continue
        helper = helpers_by_id.get(row.get("event_id"), row)
        start_value = parse_church_time(row.get("start_time", ""), time(19, 30))
        end_value = parse_church_time(row.get("end_time", ""), time(21, 0))
        start_at = datetime.combine(event_date, start_value, tzinfo=LOCAL_TIMEZONE)
        end_at = datetime.combine(event_date, end_value, tzinfo=LOCAL_TIMEZONE)
        if end_at <= start_at:
            end_at += timedelta(days=1)
        planning_details = [
            f"經文：{helper.get('bible_passage')}" if helper.get("bible_passage") else "",
            f"帶領：{helper.get('leader')}" if helper.get("leader") else "",
            "協助：" + "、".join(
                name for name in [helper.get("helper_one", ""), helper.get("helper_two", "")] if name
            ) if helper.get("helper_one") or helper.get("helper_two") else "",
            str(helper.get("internal_notes") or ""),
        ]
        normalized.append({
            "id": row.get("event_id") or f"church:{event_date}:{row.get('title', '')}",
            "date": event_date,
            "start": start_at,
            "end": end_at,
            "title": row.get("title") or helper.get("title") or "Church event",
            "person": "Church",
            "category": "Church",
            "source": "S&L Public + Helpers",
            "location": row.get("location") or helper.get("location") or "",
            "details": "\n".join(item for item in planning_details if item),
            "status": row.get("status") or helper.get("status") or "",
            "all_day": False,
        })
    return normalized


def refresh_church_events() -> tuple[bool, str]:
    event_cache = st.session_state.setdefault("church_calendar_events", {})
    messages: list[str] = []
    successful = True
    for sheet in ("26H2-Calendar-Public", "26H2-Calendar-Helpers"):
        result = list_sheet_events(runtime.settings, sheet)
        if result.success:
            event_cache[sheet] = result.events
            messages.append(f"{sheet}: {len(result.events)}")
        else:
            successful = False
            messages.append(result.detail)
    return successful, " · ".join(messages)


st.title("All events")
st.caption("One calendar for school, soccer, recurring activities, and church planning. Church rows remain synchronized through the spreadsheet SSOT.")

month_value = st.date_input(
    "Month to display", value=today.replace(day=1), key="all_events_month"
)
month_start = month_value.replace(day=1)
month_end = date(
    month_start.year,
    month_start.month,
    month_calendar.monthrange(month_start.year, month_start.month)[1],
)
grid_start = month_start - timedelta(days=month_start.weekday())
grid_end = month_end + timedelta(days=6 - month_end.weekday())

church_cache = st.session_state.get("church_calendar_events", {})
if not church_cache and readiness["google_apps_script.update_and_sync"]:
    with st.spinner("Loading church calendars…"):
        initial_success, initial_detail = refresh_church_events()
    if not initial_success:
        st.warning(initial_detail)

with st.container(horizontal=True, vertical_alignment="center"):
    if st.button("Refresh church calendars", icon=":material/refresh:"):
        with st.spinner("Refreshing Public and Helpers events…"):
            success, detail = refresh_church_events()
        if success:
            st.toast(detail, icon=":material/check_circle:")
        else:
            st.error(detail)
    if not readiness["google_apps_script.update_and_sync"]:
        st.badge("Church adapter setup needed", color="orange")

all_events = load_family_events(grid_start, grid_end) + load_church_events()
categories = sorted({str(item["category"]) for item in all_events})
people = sorted({str(item["person"]) for item in all_events})
with st.popover("Filter events", icon=":material/filter_list:"):
    selected_categories = st.multiselect(
        "Categories", categories, default=categories, key="all_events_categories"
    )
    selected_people = st.multiselect(
        "People and groups", people, default=people, key="all_events_people"
    )
    show_cancelled = st.checkbox("Show cancelled church events", value=False)

visible_events = [
    item for item in all_events
    if item["category"] in selected_categories
    and item["person"] in selected_people
    and (show_cancelled or item["status"] not in {"已取消", "取消"})
]
month_events = [item for item in visible_events if month_start <= item["date"] <= month_end]

with st.container(horizontal=True):
    st.metric("Events this month", len(month_events), border=True)
    st.metric("School and soccer", sum(item["category"] in {"School", "Soccer"} for item in month_events), border=True)
    st.metric("Activities", sum(item["category"] == "Activity" for item in month_events), border=True)
    st.metric("Church", sum(item["category"] == "Church" for item in month_events), border=True)

category_marker = {
    "School": "▣",
    "Soccer": "●",
    "Activity": "◆",
    "Church": "✦",
    "Household": "■",
}
header_columns = st.columns(7)
for column, weekday in zip(header_columns, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
    column.caption(weekday, text_alignment="center")

weeks = month_calendar.Calendar(firstweekday=0).monthdatescalendar(month_start.year, month_start.month)
for week in weeks:
    day_columns = st.columns(7, gap="small")
    for column, calendar_day in zip(day_columns, week):
        day_events = sorted(
            [item for item in month_events if item["date"] == calendar_day],
            key=lambda item: (item["start"], str(item["title"])),
        )
        with column.container(border=True, height=185, gap=None):
            if calendar_day.month == month_start.month:
                st.markdown(f"**{calendar_day.day}**")
                for item in day_events[:4]:
                    time_text = "All day" if item["all_day"] else item["start"].strftime("%-I:%M %p")
                    marker = category_marker.get(str(item["category"]), "•")
                    st.caption(f"{marker} {time_text} · {item['person']}")
                    st.markdown(str(item["title"]))
                if len(day_events) > 4:
                    st.caption(f"+{len(day_events) - 4} more")
            else:
                st.caption(str(calendar_day.day))

st.subheader("Monthly agenda")
if not month_events:
    st.info("No events match the current filters.")
else:
    event_labels = {
        f"{item['date'].strftime('%a, %b %-d')} · "
        f"{'All day' if item['all_day'] else item['start'].strftime('%-I:%M %p')} · "
        f"{item['title']} · {item['person']}": item
        for item in sorted(month_events, key=lambda value: (value["start"], str(value["title"])))
    }
    selected_label = st.selectbox("Event details", list(event_labels))
    selected_event = event_labels[selected_label]
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"### {selected_event['title']}")
            st.badge(str(selected_event["category"]), color="blue")
            if selected_event["status"] and selected_event["status"] != "Active":
                st.badge(str(selected_event["status"]))
        if selected_event["all_day"]:
            st.write(selected_event["date"].strftime("%A, %B %-d, %Y · All day"))
        else:
            st.write(
                f"{selected_event['start'].strftime('%A, %B %-d, %Y · %-I:%M %p')}–"
                f"{selected_event['end'].strftime('%-I:%M %p')}"
            )
        st.write(f"**Person/group:** {selected_event['person']}")
        st.write(f"**Location:** {selected_event['location'] or 'Not provided'}")
        st.caption(f"Source: {selected_event['source']} · ID: {selected_event['id']}")
        if selected_event["details"]:
            st.divider()
            st.text(str(selected_event["details"]))
