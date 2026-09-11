"""Shared runtime construction for HouseholdOS Streamlit pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from householdos.config import Settings
from householdos.domain.schedule import EventCategory, RecurringActivity, ScheduleAnalysis
from householdos.infrastructure.activities import JSONRecurringActivitySource
from householdos.infrastructure.ics import ICSCalendarSource
from householdos.infrastructure.sqlite import SQLitePlanRepository
from householdos.workflows.schedule_analysis import ScheduleAnalysisWorkflow


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_CACHE_VERSION = "ministry-operations-v4"


@dataclass(frozen=True)
class AppRuntime:
    settings: Settings
    repository: SQLitePlanRepository
    week_start: date
    activities: list[RecurringActivity]
    analysis: ScheduleAnalysis


@st.cache_resource
def get_repository(
    database_path: str,
    cache_version: str = REPOSITORY_CACHE_VERSION,
) -> SQLitePlanRepository:
    # The explicit version is part of Streamlit's cache key. Imported class changes
    # do not always invalidate a cached resource during a hot reload, which can leave
    # the app holding an instance created from an older repository implementation.
    del cache_version
    repository = SQLitePlanRepository(database_path)
    repository.initialize()
    return repository


@st.cache_data(ttl="5m", max_entries=4)
def load_activities() -> list[RecurringActivity]:
    settings = Settings.from_env()
    private_path = ROOT / "data/recurring_activities.json"
    path = private_path if private_path.exists() and not settings.demo_mode else ROOT / "data/sample_recurring_activities.json"
    return JSONRecurringActivitySource(path).list_activities()


def calendar_sources() -> list[ICSCalendarSource]:
    settings = Settings.from_env()
    def source(private_name: str, sample_name: str) -> Path:
        private_path = Path(private_name).expanduser() if private_name else None
        return private_path if private_path and private_path.is_file() and not settings.demo_mode else ROOT / "data" / "sample_calendars" / sample_name

    return [
        ICSCalendarSource(source(settings.student_a_school_calendar_file, "student-a-school.ics"), "school-a", "Student A", EventCategory.SCHOOL),
        ICSCalendarSource(source(settings.student_b_school_calendar_file, "student-b-school.ics"), "school-b", "Student B", EventCategory.SCHOOL),
        ICSCalendarSource(source(settings.student_a_sports_calendar_file, "student-a-soccer.ics"), "sports-a", "Student A", EventCategory.SOCCER),
        ICSCalendarSource(source(settings.student_b_sports_calendar_file, "student-b-soccer.ics"), "sports-b", "Student B", EventCategory.SOCCER),
    ]


def get_runtime() -> AppRuntime:
    settings = Settings.from_env()
    repository = get_repository(
        str(settings.database_path), REPOSITORY_CACHE_VERSION
    )
    week_start = st.session_state.get("household_week_start", date.today())
    week_start = week_start - timedelta(days=week_start.weekday())
    activities = load_activities()
    exceptions = repository.list_schedule_exceptions(
        week_start, week_start + timedelta(days=6)
    )
    analysis = ScheduleAnalysisWorkflow().run(
        week_start, calendar_sources(), activities, exceptions
    )
    return AppRuntime(settings, repository, week_start, activities, analysis)


def event_time(event) -> str:
    if event.all_day:
        return "All day"
    return f"{event.start_at.strftime('%-I:%M %p')}–{event.end_at.strftime('%-I:%M %p')}"


def household_context(runtime: AppRuntime) -> dict[str, object]:
    tasks = runtime.repository.list_tasks(include_done=False)
    return {
        "timezone": "America/Los_Angeles",
        "week_start": runtime.analysis.week_start.isoformat(),
        "week_end": runtime.analysis.week_end.isoformat(),
        "events": [
            {
                "id": event.id,
                "person": event.person,
                "title": event.title,
                "start": event.start_at.isoformat(),
                "end": event.end_at.isoformat(),
                "all_day": event.all_day,
                "location": event.location,
                "category": event.category.value,
                "source": event.source_id,
            }
            for day in runtime.analysis.days
            for event in day.events
        ],
        "conflicts": [item.model_dump(mode="json") for item in runtime.analysis.conflicts],
        "transportation": [
            item.model_dump(mode="json") for item in runtime.analysis.transportation
        ],
        "missing_information": runtime.analysis.missing_information,
        "tasks": [task.model_dump(mode="json") for task in tasks],
        "safety": {
            "external_writes_require_approval": True,
            "approved_actions_are_not_executed_in_this_mvp": True,
        },
    }
