"""Five bounded specialist roles with typed inputs and outputs."""

from __future__ import annotations

from datetime import timedelta

from householdos.domain.capstone import (
    BriefDay,
    CandidatePlan,
    CapstonePlanningRequest,
    ConfirmedPreference,
    EvidenceBundle,
    ScheduleAgentOutput,
    ValidationReport,
)
from householdos.domain.operations import GroceryItem, HouseholdTask, TaskScope, TravelPlan
from householdos.domain.schedule import EventCategory, ScheduleAnalysis
from householdos.retrieval.keyword import KeywordKnowledgeRepository


class ScheduleCommitmentsAgent:
    role_name = "Schedule and Commitments"

    def analyze(self, analysis: ScheduleAnalysis) -> ScheduleAgentOutput:
        events = [event for day in analysis.days for event in day.events]
        findings = [item.message for item in analysis.conflicts]
        if not findings:
            findings.append("No same-person event overlaps were detected.")
        open_drivers = sum(not item.resolved for item in analysis.transportation)
        if open_drivers:
            findings.append(f"{open_drivers} transportation assignments remain open.")
        return ScheduleAgentOutput(
            events=events,
            conflicts=analysis.conflicts,
            transportation=analysis.transportation,
            findings=findings,
            missing_information=analysis.missing_information,
        )


class ResearchKnowledgeAgent:
    role_name = "Research and Knowledge"

    def __init__(self, repository: KeywordKnowledgeRepository) -> None:
        self.repository = repository

    def retrieve(self, request: CapstonePlanningRequest) -> EvidenceBundle:
        domains = [domain for domain in request.source_domains if domain != "schedule"]
        if not domains:
            return EvidenceBundle(query=request.objective)
        query = " ".join([request.objective, *request.priorities, *request.constraints])
        return self.repository.search(query, domains)


class HouseholdPlanningAgent:
    role_name = "Household Planner"

    def create_candidate(
        self,
        request: CapstonePlanningRequest,
        schedule: ScheduleAgentOutput,
        evidence: EvidenceBundle,
        tasks: list[HouseholdTask],
        preferences: list[ConfirmedPreference] | None = None,
        grocery_items: list[GroceryItem] | None = None,
        travel_plans: list[TravelPlan] | None = None,
    ) -> CandidatePlan:
        preferences = preferences or []
        grocery_items = grocery_items or []
        travel_plans = travel_plans or []
        dietary = [item.value for item in preferences if "diet" in item.key.casefold()]
        days: list[BriefDay] = []
        for offset in range(7):
            current = request.week_start + timedelta(days=offset)
            events = [event for event in schedule.events if event.start_at.date() == current]
            timed = [event for event in events if not event.all_day]
            commitments = [
                f"{'All day' if event.all_day else event.start_at.strftime('%-I:%M %p')} — "
                f"{event.person}: {event.title}"
                for event in events
            ]
            preparation = [
                f"Prepare for {event.title}: {event.description}"
                for event in timed
                if event.description
            ]
            dinner = (
                "Quick-prep dinner; menu requires household confirmation."
                if len(timed) >= 3
                else "Family dinner; menu requires household confirmation."
            )
            if dietary:
                dinner += f" Respect confirmed preference: {'; '.join(dietary)}."
            days.append(
                BriefDay(
                    date=current,
                    commitments=commitments,
                    preparation=preparation,
                    dinner_plan=dinner,
                )
            )

        logistics = []
        for need in schedule.transportation:
            departure = (
                need.depart_by.strftime("%-I:%M %p")
                if need.depart_by
                else "pending travel time"
            )
            logistics.append(
                f"{need.event_start.strftime('%a')} {need.person} {need.event_title}: "
                f"driver {need.driver}; depart {departure}."
            )
        church_tasks = [task.title for task in tasks if task.scope is TaskScope.CHURCH]
        if not church_tasks and any(item.domain == "church" for item in evidence.items):
            church_tasks = [
                "Review the Friday fellowship reminder on Wednesday.",
                "Confirm Bible study leader, two helpers, and materials.",
                "Verify and review the pastor message before Saturday 7:30 AM.",
            ]
        kids_events = [
            event
            for event in schedule.events
            if event.category in {EventCategory.SCHOOL, EventCategory.SOCCER, EventCategory.ACTIVITY}
        ]
        kids_actions = [
            f"Review {event.person}'s {event.title} on {event.start_at.strftime('%a %-I:%M %p')}."
            for event in kids_events[:8]
        ]
        for need in schedule.transportation:
            if not need.resolved:
                kids_actions.append(
                    f"Confirm a driver for {need.person}'s {need.event_title} on {need.event_start.strftime('%A')}."
                )

        groceries = [
            f"{item.name} — {item.quantity} ({item.category}; for {item.needed_for})"
            for item in grocery_items
        ]
        if not groceries:
            groceries = [
                "Meal ingredients — finalize after menu choices are confirmed."
                + (f" Dietary requirement: {'; '.join(dietary)}." if dietary else "")
            ]

        travel_actions = [
            f"{trip.title}: {trip.origin} → {trip.destination}, "
            f"{trip.depart_date.strftime('%b %-d')}–{trip.return_date.strftime('%b %-d')} "
            f"({trip.status.value})."
            for trip in travel_plans
        ]
        if not travel_actions:
            travel_actions = ["No active family trip is recorded; local driving remains under logistics."]

        maintenance_actions = [
            task.title for task in tasks if task.scope is TaskScope.MAINTENANCE
        ]
        if not maintenance_actions:
            maintenance_actions = ["No open house-maintenance task is recorded for this week."]

        open_questions = list(schedule.missing_information)
        if not grocery_items:
            open_questions.append("Which meals should drive this week's grocery list?")
        return CandidatePlan(
            title=f"Household brief · {request.week_start.strftime('%b %-d')}",
            summary=(
                f"Seven-day proposal with {len(schedule.events)} commitments, "
                f"{len(schedule.conflicts)} hard conflict(s), and "
                f"{sum(not item.resolved for item in schedule.transportation)} open driver assignment(s)."
            ),
            priorities=request.priorities or ["Resolve hard conflicts and open transportation."],
            schedule_findings=schedule.findings,
            days=days,
            grocery_list=groceries,
            logistics=logistics,
            community_tasks=church_tasks,
            kids_activity_actions=list(dict.fromkeys(kids_actions)),
            church_actions=church_tasks,
            travel_actions=travel_actions,
            maintenance_actions=maintenance_actions,
            evidence_refs=[item.source_id for item in evidence.items],
            assumptions=[
                "Recurring activity times and the imported read-only calendars are current.",
                "Meal suggestions are planning placeholders, not confirmed menus.",
            ]
            + [
                f"Confirmed preference {item.key}={item.value} (owner {item.owner}; source {item.source})."
                for item in preferences
            ],
            open_questions=list(dict.fromkeys(open_questions)),
        )

    def revise(self, candidate: CandidatePlan, report: ValidationReport) -> CandidatePlan:
        revised = candidate.model_copy(deep=True)
        revised.assumptions.extend(
            f"Revision requested by critic: {item}" for item in report.revision_requests
        )
        if not revised.grocery_list:
            revised.grocery_list = ["Grocery list pending confirmed meals and dietary constraints."]
        return revised


class CriticSafetyAgent:
    role_name = "Critic and Safety"

    def validate(
        self,
        candidate: CandidatePlan,
        schedule: ScheduleAgentOutput,
        evidence: EvidenceBundle,
    ) -> ValidationReport:
        hard: list[str] = []
        warnings: list[str] = []
        missing_evidence: list[str] = []
        approval_violations: list[str] = []
        revisions: list[str] = []
        score = 100
        if len(candidate.days) != 7:
            hard.append("Weekly brief must contain exactly seven days.")
            score -= 30
        unsurfaced = [
            conflict for conflict in schedule.conflicts
            if not any(conflict.message in finding for finding in candidate.schedule_findings)
        ]
        if unsurfaced:
            hard.append("A deterministic schedule conflict is absent from the brief.")
            score -= 30
        if evidence.items and not candidate.evidence_refs:
            missing_evidence.append("Retrieved evidence was not cited by source ID.")
            score -= 10
        if not candidate.grocery_list:
            revisions.append("Add a grocery section or explicitly label it pending.")
            score -= 10
        domain_sections = {
            "kids activities": candidate.kids_activity_actions,
            "church events": candidate.church_actions,
            "groceries": candidate.grocery_list,
            "travel": candidate.travel_actions,
            "house maintenance": candidate.maintenance_actions,
        }
        for domain, items in domain_sections.items():
            if not items:
                revisions.append(f"Add an explicit {domain} section, even when no action is due.")
                score -= 5
        prohibited_claims = ("was sent", "has been booked", "calendar was updated", "purchase completed")
        serialized = candidate.model_dump_json().casefold()
        if any(claim in serialized for claim in prohibited_claims):
            approval_violations.append("The plan claims an external action completed without verification.")
            score -= 30
        if schedule.missing_information:
            warnings.extend(schedule.missing_information)
        passed = not hard and not approval_violations and score >= 80
        return ValidationReport(
            passed=passed,
            score=max(0, score),
            hard_violations=hard,
            warnings=warnings,
            missing_evidence=missing_evidence,
            approval_violations=approval_violations,
            revision_requests=revisions,
        )


class ChiefOfStaffSupervisor:
    role_name = "Chief of Staff"

    @staticmethod
    def select_route(request: CapstonePlanningRequest) -> list[str]:
        route = ["Schedule and Commitments"]
        if any(domain != "schedule" for domain in request.source_domains):
            route.append("Research and Knowledge")
        route.extend(["Household Planner", "Critic and Safety", "Chief of Staff"])
        return route
