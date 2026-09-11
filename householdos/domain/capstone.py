"""Typed contracts for the capstone multi-agent weekly-planning workflow."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from householdos.domain.schedule import CalendarEvent, ScheduleConflict, TransportationNeed


class AgentRole(str, Enum):
    SUPERVISOR = "Chief of Staff"
    SCHEDULE = "Schedule and Commitments"
    RESEARCH = "Research and Knowledge"
    PLANNER = "Household Planner"
    CRITIC = "Critic and Safety"


class CapstonePlanningRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    week_start: date
    objective: str = "Plan the household week"
    priorities: list[str] = Field(default_factory=list, max_length=12)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    planning_domains: list[str] = Field(
        default_factory=lambda: [
            "kids activities",
            "church events",
            "groceries",
            "travel",
            "house maintenance",
        ]
    )
    source_domains: list[str] = Field(
        default_factory=lambda: ["schedule", "household", "church"]
    )


class TaskEnvelope(BaseModel):
    request_id: str
    role: AgentRole
    objective: str
    constraints: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    status: str = "Pending"


class EvidenceItem(BaseModel):
    source_id: str
    title: str
    timestamp: str
    owner: str
    sensitivity: str
    domain: str
    excerpt: str
    relevance_score: float = Field(ge=0, le=1)


class EvidenceBundle(BaseModel):
    query: str
    items: list[EvidenceItem] = Field(default_factory=list, max_length=4)
    missing_domains: list[str] = Field(default_factory=list)


class ScheduleAgentOutput(BaseModel):
    events: list[CalendarEvent]
    conflicts: list[ScheduleConflict]
    transportation: list[TransportationNeed]
    findings: list[str]
    missing_information: list[str]


class BriefDay(BaseModel):
    date: date
    commitments: list[str] = Field(default_factory=list)
    preparation: list[str] = Field(default_factory=list)
    dinner_plan: str


class CandidatePlan(BaseModel):
    title: str
    summary: str
    priorities: list[str]
    schedule_findings: list[str]
    days: list[BriefDay] = Field(min_length=7, max_length=7)
    grocery_list: list[str]
    logistics: list[str]
    community_tasks: list[str]
    kids_activity_actions: list[str] = Field(default_factory=list)
    church_actions: list[str] = Field(default_factory=list)
    travel_actions: list[str] = Field(default_factory=list)
    maintenance_actions: list[str] = Field(default_factory=list)
    evidence_refs: list[str]
    assumptions: list[str]
    open_questions: list[str]
    approval_request_ids: list[int] = Field(default_factory=list)


class ValidationReport(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    hard_violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    approval_violations: list[str] = Field(default_factory=list)
    revision_requests: list[str] = Field(default_factory=list)


class RunStep(BaseModel):
    sequence: int
    role: AgentRole
    action: str
    status: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    evidence_refs: list[str] = Field(default_factory=list)
    summary: str
    error: str | None = None


class RunTrace(BaseModel):
    run_id: str
    request_id: str
    route: list[AgentRole]
    steps: list[RunStep]
    revision_count: int = Field(ge=0, le=1)
    started_at: datetime
    completed_at: datetime
    total_duration_ms: int


class WeeklyBrief(BaseModel):
    request_id: str
    run_id: str
    title: str
    summary: str
    priorities: list[str]
    schedule_findings: list[str]
    days: list[BriefDay] = Field(min_length=7, max_length=7)
    grocery_list: list[str]
    logistics: list[str]
    community_tasks: list[str]
    kids_activity_actions: list[str] = Field(default_factory=list)
    church_actions: list[str] = Field(default_factory=list)
    travel_actions: list[str] = Field(default_factory=list)
    maintenance_actions: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem]
    assumptions: list[str]
    open_questions: list[str]
    approval_request_ids: list[int]
    validation: ValidationReport


class ConfirmedPreference(BaseModel):
    key: str
    value: str
    owner: str
    source: str
    effective_date: date
    sensitivity: str = "Household"
    confirmed_at: str
