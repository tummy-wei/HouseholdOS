"""Ports for read-only calendar and recurring-activity sources."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from householdos.domain.schedule import CalendarEvent, RecurringActivity


class CalendarSource(Protocol):
    source_id: str

    def events_between(self, start: date, end: date) -> list[CalendarEvent]: ...


class RecurringActivitySource(Protocol):
    def list_activities(self) -> list[RecurringActivity]: ...

