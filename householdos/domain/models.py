"""Typed inputs and outputs for weekly planning."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator


class WeeklyPlanningRequest(BaseModel):
    week_start: date
    priorities: list[str] = Field(min_length=1, max_length=12)
    commitments: list[str] = Field(default_factory=list, max_length=30)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    calendar_context: list[str] = Field(default_factory=list, max_length=80)


class DailyPlan(BaseModel):
    date: date
    theme: str = Field(min_length=1, max_length=120)
    tasks: list[str] = Field(default_factory=list, max_length=10)


class WeeklyPlan(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1200)
    days: list[DailyPlan] = Field(min_length=7, max_length=7)
    open_questions: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def dates_are_unique_and_ordered(self) -> "WeeklyPlan":
        dates = [day.date for day in self.days]
        if dates != sorted(dates) or len(set(dates)) != 7:
            raise ValueError("Weekly plan days must contain seven unique, ordered dates")
        return self


class WeeklyPlanRecord(BaseModel):
    id: int
    week_start: date
    title: str
    created_at: str


class ApprovalRequestRecord(BaseModel):
    id: int
    tool_name: str
    action: str
    target: str
    payload: dict[str, Any]
    status: str
    requested_at: str
    decided_at: str | None = None
    executed_at: str | None = None
    execution_status: str | None = None
    execution_detail: str | None = None
