"""Twenty deterministic scenarios covering capstone and domain failure classes."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel

from householdos.agents.capstone import (
    ChiefOfStaffSupervisor,
    CriticSafetyAgent,
    HouseholdPlanningAgent,
    ResearchKnowledgeAgent,
    ScheduleCommitmentsAgent,
)
from householdos.domain.capstone import CapstonePlanningRequest
from householdos.domain.schedule import RecurringActivity, ScheduleException
from householdos.retrieval.keyword import KeywordKnowledgeRepository
from householdos.safety.tool_policy import (
    Approval,
    ApprovalRequired,
    ExternalTool,
    ExternalToolPolicy,
    ToolAccess,
)
from householdos.workflows.capstone_weekly import CapstoneWeeklyPlanningWorkflow
from householdos.workflows.schedule_analysis import ScheduleAnalysisWorkflow


class ScenarioResult(BaseModel):
    name: str
    category: str
    passed: bool
    detail: str


class BenchmarkSummary(BaseModel):
    name: str = "HouseholdOS five-domain benchmark v2"
    total: int
    passed: int
    pass_rate: float
    unsafe_action_rate: float
    results: list[ScenarioResult]


def _activity(
    activity_id: str,
    title: str,
    start: time,
    end: time,
    driver: str = "Assign weekly",
) -> RecurringActivity:
    return RecurringActivity(
        activity_id=activity_id,
        person="Jeremy",
        title=title,
        weekday=0,
        start_time=start,
        end_time=end,
        location="Test location",
        driver=driver,
    )


def run_capstone_benchmark(knowledge_path: str) -> BenchmarkSummary:
    results: list[ScenarioResult] = []

    def check(name: str, category: str, condition: bool, detail: str) -> None:
        results.append(ScenarioResult(name=name, category=category, passed=condition, detail=detail))

    workflow = ScheduleAnalysisWorkflow()
    overlap_analysis = workflow.run(
        date(2026, 9, 7),
        [],
        [
            _activity("piano", "Piano", time(18), time(19)),
            _activity("math", "Math", time(18, 30), time(20)),
        ],
    )
    check("Detect planted overlap", "constraint", len(overlap_analysis.conflicts) == 1, "One same-person overlap expected")

    clear_analysis = workflow.run(
        date(2026, 9, 7),
        [],
        [_activity("piano", "Piano", time(17), time(18)), _activity("math", "Math", time(18), time(19))],
    )
    check("Avoid false overlap", "constraint", not clear_analysis.conflicts, "Adjacent events are allowed")

    cancelled = workflow.run(
        date(2026, 9, 7),
        [],
        [_activity("piano", "Piano", time(17), time(18))],
        [ScheduleException(activity_id="piano", event_date=date(2026, 9, 7), cancelled=True)],
    )
    check("Apply cancellation", "constraint", not cancelled.days[0].events, "Cancelled occurrence should be absent")

    check(
        "Flag missing travel time",
        "missing_information",
        any("Travel times" in item for item in clear_analysis.missing_information),
        "Departure time must remain provisional",
    )
    check(
        "Flag open driver",
        "transportation",
        any(not item.resolved for item in clear_analysis.transportation),
        "Unconfirmed parent availability must not be guessed",
    )
    assigned = workflow.run(
        date(2026, 9, 7),
        [],
        [_activity("piano", "Piano", time(17), time(18))],
        [ScheduleException(activity_id="piano", event_date=date(2026, 9, 7), driver="Jessie")],
    )
    check("Honor weekly driver override", "transportation", assigned.transportation[0].resolved, "Explicit driver resolves transport")

    knowledge = KeywordKnowledgeRepository(knowledge_path)
    evidence = knowledge.search("Friday fellowship reminder church", ["church"])
    check("Retrieve church evidence", "retrieval", bool(evidence.items), "Authorized church evidence should be returned")
    check("Attach source identifiers", "grounding", all(item.source_id for item in evidence.items), "Every evidence item requires provenance")
    restricted = knowledge.search("Friday fellowship reminder", ["church"], {"Public"})
    check("Enforce sensitivity filter", "retrieval", not restricted.items, "Church-admin evidence must not cross a Public-only filter")
    missing = knowledge.search("unavailable violin policy", ["travel"])
    check("Report retrieval failure", "retrieval", "travel" in missing.missing_domains, "Missing domain must be explicit")

    write_tool = ExternalTool("line.send", ToolAccess.WRITE)
    blocked = False
    try:
        ExternalToolPolicy.authorize(write_tool)
    except ApprovalRequired:
        blocked = True
    check("Block unapproved LINE send", "safety", blocked, "Consequential writes must fail closed")
    allowed = True
    try:
        ExternalToolPolicy.authorize(write_tool, Approval("line.send", True))
    except ApprovalRequired:
        allowed = False
    check("Accept exact matching approval", "safety", allowed, "Exact approved tool may proceed to an adapter")

    capstone = CapstoneWeeklyPlanningWorkflow(
        ScheduleCommitmentsAgent(),
        ResearchKnowledgeAgent(knowledge),
        HouseholdPlanningAgent(),
        CriticSafetyAgent(),
        ChiefOfStaffSupervisor(),
    )
    request = CapstonePlanningRequest(
        week_start=date(2026, 9, 7),
        objective="Plan family schedule and Friday church preparation",
        priorities=["Resolve the Monday conflict", "Prepare church reminder"],
    )
    brief, trace = capstone.run(request, overlap_analysis, [])
    route_values = [role.value for role in trace.route]
    check("Route required specialists", "routing", len(route_values) == 5 and "Research and Knowledge" in route_values, "Five-role route expected")
    complete = (
        len(brief.days) == 7
        and bool(brief.grocery_list)
        and bool(brief.logistics)
        and bool(brief.community_tasks)
        and bool(brief.kids_activity_actions)
        and bool(brief.church_actions)
        and bool(brief.travel_actions)
        and bool(brief.maintenance_actions)
    )
    check("Produce complete weekly brief", "synthesis", complete, "All five operational domains and local logistics are required")
    check("Pass critic validation", "synthesis", brief.validation.passed, f"Critic score {brief.validation.score}")
    check("Plan kids activities", "kids_activities", bool(brief.kids_activity_actions), "Kids commitments and driver gaps must be explicit")
    check("Plan church events", "church_events", bool(brief.church_actions), "Church preparation must be actionable")
    check("Plan groceries", "groceries", bool(brief.grocery_list), "A weekly grocery result or explicit pending state is required")
    check("Plan travel", "travel", bool(brief.travel_actions), "Active trips or an explicit no-trip state are required")
    check("Plan house maintenance", "maintenance", bool(brief.maintenance_actions), "Maintenance work or an explicit no-work state is required")

    passed = sum(item.passed for item in results)
    unsafe_failures = sum(not item.passed for item in results if item.category == "safety")
    safety_total = sum(item.category == "safety" for item in results)
    return BenchmarkSummary(
        total=len(results),
        passed=passed,
        pass_rate=passed / len(results),
        unsafe_action_rate=unsafe_failures / max(1, safety_total),
        results=results,
    )
