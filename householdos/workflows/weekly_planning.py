"""Orchestration for creating and saving a weekly plan."""

from datetime import timedelta

from householdos.domain.models import WeeklyPlan, WeeklyPlanningRequest
from householdos.ports.planning import PlanRepository, WeeklyPlanner


class WeeklyPlanningWorkflow:
    def __init__(self, planner: WeeklyPlanner, repository: PlanRepository) -> None:
        self._planner = planner
        self._repository = repository

    def run(self, request: WeeklyPlanningRequest) -> WeeklyPlan:
        plan = self._planner.create_plan(request)
        expected_dates = [request.week_start + timedelta(days=index) for index in range(7)]
        if [day.date for day in plan.days] != expected_dates:
            raise ValueError("Generated plan dates do not match the requested week")
        self._repository.save(request, plan)
        return plan
