"""Deterministic calendar merge, exception handling, and conflict analysis."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from householdos.domain.schedule import (
    CalendarEvent,
    ConflictSeverity,
    DaySchedule,
    EventCategory,
    RecurringActivity,
    ScheduleAnalysis,
    ScheduleConflict,
    ScheduleException,
    TransportationNeed,
)
from householdos.ports.calendar import CalendarSource


class ScheduleAnalysisWorkflow:
    def __init__(self, timezone: str = "America/Los_Angeles") -> None:
        self.timezone = ZoneInfo(timezone)

    def run(
        self,
        week_start: date,
        calendar_sources: list[CalendarSource],
        activities: list[RecurringActivity],
        exceptions: list[ScheduleException] | None = None,
    ) -> ScheduleAnalysis:
        week_end = week_start + timedelta(days=6)
        events = [
            event
            for source in calendar_sources
            for event in source.events_between(week_start, week_end)
        ]
        events.extend(self._expand_activities(week_start, activities, exceptions or []))
        events = self._deduplicate(events)
        events.sort(key=lambda event: (event.start_at, event.person, event.title))

        days = [
            DaySchedule(
                date=week_start + timedelta(days=index),
                events=[event for event in events if event.start_at.date() == week_start + timedelta(days=index)],
            )
            for index in range(7)
        ]
        conflicts = self._find_conflicts(events)
        transportation = self._transportation_needs(events, activities, exceptions or [])
        missing = self._missing_information(activities, transportation)
        source_counts = dict(Counter(event.source_id for event in events))
        return ScheduleAnalysis(
            week_start=week_start,
            week_end=week_end,
            days=days,
            conflicts=conflicts,
            transportation=transportation,
            missing_information=missing,
            source_event_counts=source_counts,
        )

    def _expand_activities(
        self,
        week_start: date,
        activities: list[RecurringActivity],
        exceptions: list[ScheduleException],
    ) -> list[CalendarEvent]:
        exception_index = {(item.activity_id, item.event_date): item for item in exceptions}
        results: list[CalendarEvent] = []
        for activity in activities:
            if not activity.active:
                continue
            event_date = week_start + timedelta(days=(activity.weekday - week_start.weekday()) % 7)
            if not week_start <= event_date <= week_start + timedelta(days=6):
                continue
            if activity.start_date and event_date < activity.start_date:
                continue
            if activity.end_date and event_date > activity.end_date:
                continue
            exception = exception_index.get((activity.activity_id, event_date))
            if exception and exception.cancelled:
                continue
            start_time = exception.new_start_time if exception and exception.new_start_time else activity.start_time
            end_time = exception.new_end_time if exception and exception.new_end_time else activity.end_time
            start_at = datetime.combine(event_date, start_time, tzinfo=self.timezone)
            end_at = datetime.combine(event_date, end_time, tzinfo=self.timezone)
            if end_at <= start_at:
                end_at += timedelta(days=1)
            location = exception.new_location if exception and exception.new_location else activity.location
            results.append(
                CalendarEvent(
                    id=f"activity:{activity.activity_id}:{event_date.isoformat()}",
                    source_id="recurring-activities",
                    person=activity.person,
                    title=activity.title,
                    start_at=start_at,
                    end_at=end_at,
                    category=EventCategory.SOCCER if "soccer" in activity.title.lower() else EventCategory.ACTIVITY,
                    location=location or "",
                    description=activity.preparation,
                    authoritative=False,
                )
            )
        return results

    @staticmethod
    def _deduplicate(events: list[CalendarEvent]) -> list[CalendarEvent]:
        """Prefer authoritative feeds over a matching manually recurring event."""
        kept: list[CalendarEvent] = []
        for event in sorted(events, key=lambda item: item.authoritative, reverse=True):
            duplicate = any(
                not event.all_day
                and not other.all_day
                and
                other.person == event.person
                and other.start_at.date() == event.start_at.date()
                and other.category == event.category
                and abs((other.start_at - event.start_at).total_seconds()) <= 45 * 60
                and ScheduleAnalysisWorkflow._event_kind(other)
                == ScheduleAnalysisWorkflow._event_kind(event)
                for other in kept
            )
            if not duplicate:
                kept.append(event)
        return kept

    @staticmethod
    def _event_kind(event: CalendarEvent) -> str:
        title = event.title.lower()
        if event.category is EventCategory.SOCCER:
            if "game" in title or "match" in title:
                return "soccer-game"
            if "training" in title or "practice" in title or "soccer" in title:
                return "soccer-training"
        return f"{event.category.value}:{title}"

    @staticmethod
    def _find_conflicts(events: list[CalendarEvent]) -> list[ScheduleConflict]:
        conflicts: list[ScheduleConflict] = []
        timed = [event for event in events if not event.all_day]
        for index, first in enumerate(timed):
            for second in timed[index + 1 :]:
                if second.start_at.date() != first.start_at.date():
                    if second.start_at.date() > first.start_at.date():
                        break
                    continue
                if first.person != second.person:
                    continue
                if first.start_at < second.end_at and second.start_at < first.end_at:
                    conflicts.append(
                        ScheduleConflict(
                            kind="overlap",
                            severity=ConflictSeverity.HARD,
                            message=f"{first.person}: {first.title} overlaps {second.title}.",
                            event_ids=[first.id, second.id],
                        )
                    )
        return conflicts

    def _transportation_needs(
        self,
        events: list[CalendarEvent],
        activities: list[RecurringActivity],
        exceptions: list[ScheduleException],
    ) -> list[TransportationNeed]:
        activity_index = {activity.activity_id: activity for activity in activities}
        exception_index = {(item.activity_id, item.event_date): item for item in exceptions}
        needs: list[TransportationNeed] = []
        for event in events:
            if event.all_day or event.location.strip().lower() in {"", "home", "online"}:
                continue
            activity = None
            exception = None
            if event.id.startswith("activity:"):
                activity_id = event.id.split(":", 2)[1]
                activity = activity_index.get(activity_id)
                exception = exception_index.get((activity_id, event.start_at.date()))
            elif event.category is not EventCategory.SOCCER:
                continue
            driver = (
                exception.driver
                if exception and exception.driver
                else activity.driver if activity else "Assign weekly"
            )
            buffer_min = activity.arrival_buffer_min if activity else 15
            travel_min = activity.travel_min if activity else None
            arrive_by = event.start_at - timedelta(minutes=buffer_min)
            depart_by = (
                arrive_by - timedelta(minutes=travel_min)
                if travel_min is not None
                else None
            )
            needs.append(
                TransportationNeed(
                    event_id=event.id,
                    person=event.person,
                    event_title=event.title,
                    event_start=event.start_at,
                    location=event.location,
                    arrive_by=arrive_by,
                    depart_by=depart_by,
                    driver=driver,
                    resolved=driver.strip().lower() not in {"", "assign weekly", "tbd"},
                )
            )
        return needs

    @staticmethod
    def _missing_information(
        activities: list[RecurringActivity], transportation: list[TransportationNeed]
    ) -> list[str]:
        missing: list[str] = []
        if any(not activity.location for activity in activities if activity.active):
            missing.append("One or more active recurring activities has no location.")
        if any(activity.travel_min is None and activity.location.lower() not in {"", "home", "online"} for activity in activities if activity.active):
            missing.append("Travel times are not configured; departure deadlines are provisional.")
        unresolved = sum(not need.resolved for need in transportation)
        if unresolved:
            missing.append(f"{unresolved} off-site driver assignment(s) remain open for this week.")
        return missing
