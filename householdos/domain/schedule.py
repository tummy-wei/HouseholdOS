"""Domain contracts for calendar normalization and household schedule analysis."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class EventCategory(str, Enum):
    SCHOOL = "School"
    SOCCER = "Soccer"
    ACTIVITY = "Activity"
    CHURCH = "Church"
    HOUSEHOLD = "Household"


class CalendarEvent(BaseModel):
    id: str
    source_id: str
    person: str
    title: str
    start_at: datetime
    end_at: datetime
    category: EventCategory = EventCategory.HOUSEHOLD
    location: str = ""
    description: str = ""
    all_day: bool = False
    authoritative: bool = True

    @model_validator(mode="after")
    def end_follows_start(self) -> "CalendarEvent":
        if self.end_at <= self.start_at:
            raise ValueError("Calendar event end must follow its start")
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Calendar event timestamps must be timezone-aware")
        return self


class RecurringActivity(BaseModel):
    activity_id: str
    person: str
    title: str
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    location: str = ""
    start_date: date | None = None
    end_date: date | None = None
    travel_min: int | None = Field(default=None, ge=0, le=240)
    arrival_buffer_min: int = Field(default=15, ge=0, le=120)
    driver: str = "Assign weekly"
    preparation: str = ""
    active: bool = True


class ScheduleException(BaseModel):
    activity_id: str
    event_date: date
    cancelled: bool = False
    new_start_time: time | None = None
    new_end_time: time | None = None
    new_location: str | None = None
    driver: str | None = None
    note: str = ""


class ConflictSeverity(str, Enum):
    INFO = "Info"
    WARNING = "Warning"
    HARD = "Hard"


class ScheduleConflict(BaseModel):
    kind: str
    severity: ConflictSeverity
    message: str
    event_ids: list[str] = Field(min_length=1)


class TransportationNeed(BaseModel):
    event_id: str
    person: str
    event_title: str
    event_start: datetime
    location: str
    arrive_by: datetime
    depart_by: datetime | None = None
    driver: str = "Assign weekly"
    resolved: bool = False


class DaySchedule(BaseModel):
    date: date
    events: list[CalendarEvent] = Field(default_factory=list)


class ScheduleAnalysis(BaseModel):
    week_start: date
    week_end: date
    days: list[DaySchedule]
    conflicts: list[ScheduleConflict] = Field(default_factory=list)
    transportation: list[TransportationNeed] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    source_event_counts: dict[str, int] = Field(default_factory=dict)

