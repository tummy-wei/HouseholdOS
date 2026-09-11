"""Observable five-role capstone workflow with one bounded critic revision."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from householdos.agents.capstone import (
    ChiefOfStaffSupervisor,
    CriticSafetyAgent,
    HouseholdPlanningAgent,
    ResearchKnowledgeAgent,
    ScheduleCommitmentsAgent,
)
from householdos.domain.capstone import (
    AgentRole,
    CapstonePlanningRequest,
    RunStep,
    RunTrace,
    WeeklyBrief,
    ConfirmedPreference,
)
from householdos.domain.operations import GroceryItem, HouseholdTask, TravelPlan
from householdos.domain.schedule import ScheduleAnalysis


class CapstoneWeeklyPlanningWorkflow:
    def __init__(
        self,
        schedule_agent: ScheduleCommitmentsAgent,
        research_agent: ResearchKnowledgeAgent,
        planning_agent: HouseholdPlanningAgent,
        critic_agent: CriticSafetyAgent,
        supervisor: ChiefOfStaffSupervisor,
        repository=None,
    ) -> None:
        self.schedule_agent = schedule_agent
        self.research_agent = research_agent
        self.planning_agent = planning_agent
        self.critic_agent = critic_agent
        self.supervisor = supervisor
        self.repository = repository

    def run(
        self,
        request: CapstonePlanningRequest,
        analysis: ScheduleAnalysis,
        tasks: list[HouseholdTask],
        preferences: list[ConfirmedPreference] | None = None,
        grocery_items: list[GroceryItem] | None = None,
        travel_plans: list[TravelPlan] | None = None,
    ) -> tuple[WeeklyBrief, RunTrace]:
        run_id = str(uuid4())
        run_started = datetime.now(UTC)
        steps: list[RunStep] = []

        def record(role: AgentRole, action: str, operation):
            started = datetime.now(UTC)
            output = operation()
            completed = datetime.now(UTC)
            evidence_refs = []
            if hasattr(output, "items"):
                evidence_refs = [item.source_id for item in output.items]
            steps.append(
                RunStep(
                    sequence=len(steps) + 1,
                    role=role,
                    action=action,
                    status="Completed",
                    started_at=started,
                    completed_at=completed,
                    duration_ms=max(0, int((completed - started).total_seconds() * 1000)),
                    evidence_refs=evidence_refs,
                    summary=type(output).__name__,
                )
            )
            return output

        schedule = record(
            AgentRole.SCHEDULE,
            "Normalize events and detect conflicts",
            lambda: self.schedule_agent.analyze(analysis),
        )
        evidence = record(
            AgentRole.RESEARCH,
            "Retrieve authorized household and ministry evidence",
            lambda: self.research_agent.retrieve(request),
        )
        candidate = record(
            AgentRole.PLANNER,
            "Synthesize kids, church, grocery, travel, and maintenance work",
            lambda: self.planning_agent.create_candidate(
                request,
                schedule,
                evidence,
                tasks,
                preferences or [],
                grocery_items or [],
                travel_plans or [],
            ),
        )
        validation = record(
            AgentRole.CRITIC,
            "Validate feasibility, grounding, completeness, and approval boundaries",
            lambda: self.critic_agent.validate(candidate, schedule, evidence),
        )
        revision_count = 0
        if not validation.passed and validation.revision_requests:
            revision_count = 1
            candidate = record(
                AgentRole.PLANNER,
                "Apply one targeted critic revision",
                lambda: self.planning_agent.revise(candidate, validation),
            )
            validation = record(
                AgentRole.CRITIC,
                "Revalidate revised candidate",
                lambda: self.critic_agent.validate(candidate, schedule, evidence),
            )

        completed = datetime.now(UTC)
        steps.append(
            RunStep(
                sequence=len(steps) + 1,
                role=AgentRole.SUPERVISOR,
                action="Reconcile specialist outputs into the final weekly brief",
                status="Completed" if validation.passed else "Needs review",
                started_at=completed,
                completed_at=completed,
                duration_ms=0,
                evidence_refs=candidate.evidence_refs,
                summary="WeeklyBrief",
            )
        )
        trace = RunTrace(
            run_id=run_id,
            request_id=request.request_id,
            route=[AgentRole(item) for item in self.supervisor.select_route(request)],
            steps=steps,
            revision_count=revision_count,
            started_at=run_started,
            completed_at=completed,
            total_duration_ms=max(0, int((completed - run_started).total_seconds() * 1000)),
        )
        brief = WeeklyBrief(
            request_id=request.request_id,
            run_id=run_id,
            **candidate.model_dump(),
            evidence=evidence.items,
            validation=validation,
        )
        if self.repository is not None:
            self.repository.save_capstone_run(request, brief, trace)
        return brief, trace
