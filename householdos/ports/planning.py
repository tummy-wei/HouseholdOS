"""Ports for planning and persistence implementations."""

from __future__ import annotations

from typing import Protocol

from householdos.domain.models import (
    WeeklyPlan,
    WeeklyPlanRecord,
    WeeklyPlanningRequest,
)


class WeeklyPlanner(Protocol):
    def create_plan(self, request: WeeklyPlanningRequest) -> WeeklyPlan: ...


class PlanRepository(Protocol):
    def save(self, request: WeeklyPlanningRequest, plan: WeeklyPlan) -> int: ...

    def list_recent(self, limit: int = 5) -> list[WeeklyPlanRecord]: ...
