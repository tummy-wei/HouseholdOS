"""Operational contracts for tasks, event briefs, chat, and ministry drafts."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskScope(str, Enum):
    PARENTS = "Parents"
    CHURCH = "Church"
    HOUSEHOLD = "Household"
    KIDS = "Kids"
    GROCERY = "Grocery"
    TRAVEL = "Travel"
    MAINTENANCE = "Maintenance"


class TaskPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TaskStatus(str, Enum):
    TODO = "To do"
    IN_PROGRESS = "In progress"
    DONE = "Done"


class HouseholdTask(BaseModel):
    id: int
    title: str
    scope: TaskScope
    owner: str = "Unassigned"
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    source: str = "Manual"
    notes: str = ""
    created_at: str


class NewHouseholdTask(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    scope: TaskScope
    owner: str = Field(default="Unassigned", max_length=120)
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    source: str = Field(default="Manual", max_length=120)
    notes: str = Field(default="", max_length=1000)


class EventOnePager(BaseModel):
    event_id: str
    title: str
    event_date: date
    markdown: str
    filename: str
    generated_at: datetime


class PastorMessageDraft(BaseModel):
    subject: str
    sender: str
    pastor_name: str
    original_body: str
    line_message: str
    source_type: str = "Pasted email"
    warnings: list[str] = Field(default_factory=list)


class MinistryWorkflowType(str, Enum):
    FELLOWSHIP_REMINDER = "Friday fellowship reminder"
    ONLINE_PRAYER = "Saturday online prayer"
    SUNDAY_FORECAST = "Sunday message forecast"
    BIBLE_COWORK_PREP = "Bible cowork preparation"


class MinistryDraftStatus(str, Enum):
    DRAFT = "Draft"
    PROPOSED = "Proposed"
    APPROVED = "Approved"
    SENT = "Sent"
    REJECTED = "Rejected"
    FAILED = "Failed"


class MinistryDraft(BaseModel):
    id: int
    workflow_type: MinistryWorkflowType
    title: str
    destination: str
    message: str
    scheduled_for: datetime | None = None
    source_type: str = "Manual"
    source_ref: str = ""
    source_timestamp: datetime | None = None
    status: MinistryDraftStatus = MinistryDraftStatus.DRAFT
    approval_request_id: int | None = None
    created_at: str
    updated_at: str


class NewMinistryDraft(BaseModel):
    workflow_type: MinistryWorkflowType
    title: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=5000)
    scheduled_for: datetime | None = None
    source_type: str = Field(default="Manual", max_length=100)
    source_ref: str = Field(default="", max_length=500)
    source_timestamp: datetime | None = None


class BibleStudyMaterial(BaseModel):
    id: int
    title: str
    passage: str
    study_date: date | None = None
    drive_url: str
    storage_location: str
    status: str
    notes: str
    created_at: str
    updated_at: str


class NewBibleStudyMaterial(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    passage: str = Field(default="", max_length=240)
    study_date: date | None = None
    drive_url: str = Field(min_length=1, max_length=1000)
    storage_location: str = Field(default="S&L Google Drive", max_length=120)
    status: str = Field(default="Source", max_length=80)
    notes: str = Field(default="", max_length=1000)


class GroceryStatus(str, Enum):
    NEEDED = "Needed"
    PURCHASED = "Purchased"


class GroceryItem(BaseModel):
    id: int
    week_start: date
    name: str
    category: str = "Other"
    quantity: str = "1"
    needed_for: str = "Weekly household"
    assigned_to: str = "Unassigned"
    status: GroceryStatus = GroceryStatus.NEEDED
    created_at: str


class NewGroceryItem(BaseModel):
    week_start: date
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default="Other", max_length=80)
    quantity: str = Field(default="1", max_length=80)
    needed_for: str = Field(default="Weekly household", max_length=160)
    assigned_to: str = Field(default="Unassigned", max_length=120)


class TripStatus(str, Enum):
    IDEA = "Idea"
    PLANNING = "Planning"
    CONFIRMED = "Confirmed"
    COMPLETED = "Completed"


class TravelPlan(BaseModel):
    id: int
    title: str
    depart_date: date
    return_date: date
    origin: str
    destination: str
    travelers: str
    transport_mode: str
    lodging: str = ""
    confirmation_refs: str = ""
    notes: str = ""
    status: TripStatus = TripStatus.IDEA
    created_at: str


class NewTravelPlan(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    depart_date: date
    return_date: date
    origin: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    travelers: str = Field(min_length=1, max_length=300)
    transport_mode: str = Field(default="Car", max_length=80)
    lodging: str = Field(default="", max_length=240)
    confirmation_refs: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=1000)

    def model_post_init(self, __context: object) -> None:
        if self.return_date < self.depart_date:
            raise ValueError("Return date cannot be before departure date")
