"""SQLite persistence for generated weekly plans."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterator

from householdos.domain.models import (
    ApprovalRequestRecord,
    WeeklyPlan,
    WeeklyPlanRecord,
    WeeklyPlanningRequest,
)
from householdos.domain.operations import (
    BibleStudyMaterial,
    GroceryItem,
    GroceryStatus,
    HouseholdTask,
    NewGroceryItem,
    NewHouseholdTask,
    NewBibleStudyMaterial,
    NewMinistryDraft,
    NewTravelPlan,
    TaskStatus,
    TravelPlan,
    TripStatus,
    MinistryDraft,
    MinistryDraftStatus,
)
from householdos.domain.capstone import (
    CapstonePlanningRequest,
    ConfirmedPreference,
    RunTrace,
    WeeklyBrief,
)
from householdos.domain.schedule import ScheduleException


class SQLitePlanRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS weekly_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start TEXT NOT NULL,
                    title TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schedule_exceptions (
                    activity_id TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    exception_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (activity_id, event_date)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    decided_at TEXT,
                    executed_at TEXT,
                    execution_status TEXT,
                    execution_detail TEXT
                )
                """
            )
            self._ensure_column(connection, "approval_requests", "executed_at", "TEXT")
            self._ensure_column(connection, "approval_requests", "execution_status", "TEXT")
            self._ensure_column(connection, "approval_requests", "execution_detail", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS household_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    due_date TEXT,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS capstone_runs (
                    run_id TEXT PRIMARY KEY,
                    request_json TEXT NOT NULL,
                    brief_json TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS confirmed_preferences (
                    preference_key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    source TEXT NOT NULL,
                    effective_date TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    confirmed_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benchmark_name TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS grocery_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    needed_for TEXT NOT NULL,
                    assigned_to TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS travel_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    depart_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    travelers TEXT NOT NULL,
                    transport_mode TEXT NOT NULL,
                    lodging TEXT NOT NULL,
                    confirmation_refs TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ministry_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    message TEXT NOT NULL,
                    scheduled_for TEXT,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    source_timestamp TEXT,
                    status TEXT NOT NULL,
                    approval_request_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bible_study_materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    passage TEXT NOT NULL,
                    study_date TEXT,
                    drive_url TEXT NOT NULL,
                    storage_location TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection, table: str, column: str, declaration: str
    ) -> None:
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def save(self, request: WeeklyPlanningRequest, plan: WeeklyPlan) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO weekly_plans
                    (week_start, title, request_json, plan_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request.week_start.isoformat(),
                    plan.title,
                    json.dumps(request.model_dump(mode="json")),
                    json.dumps(plan.model_dump(mode="json")),
                    datetime.now(UTC).isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return an inserted plan id")
            return cursor.lastrowid

    def list_recent(self, limit: int = 5) -> list[WeeklyPlanRecord]:
        safe_limit = max(1, min(limit, 50))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, week_start, title, created_at
                FROM weekly_plans
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [WeeklyPlanRecord.model_validate(dict(row)) for row in rows]

    def save_schedule_exception(self, exception: ScheduleException) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO schedule_exceptions
                    (activity_id, event_date, exception_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(activity_id, event_date) DO UPDATE SET
                    exception_json = excluded.exception_json,
                    updated_at = excluded.updated_at
                """,
                (
                    exception.activity_id,
                    exception.event_date.isoformat(),
                    json.dumps(exception.model_dump(mode="json")),
                    now,
                ),
            )

    def list_schedule_exceptions(self, start: date, end: date) -> list[ScheduleException]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT exception_json
                FROM schedule_exceptions
                WHERE event_date BETWEEN ? AND ?
                ORDER BY event_date, activity_id
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [ScheduleException.model_validate_json(row["exception_json"]) for row in rows]

    def propose_external_action(
        self,
        tool_name: str,
        action: str,
        target: str,
        payload: dict[str, object],
    ) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO approval_requests
                    (tool_name, action, target, payload_json, status, requested_at)
                VALUES (?, ?, ?, ?, 'Proposed', ?)
                """,
                (
                    tool_name,
                    action,
                    target,
                    json.dumps(payload),
                    datetime.now(UTC).isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return an approval request id")
            return cursor.lastrowid

    def decide_external_action(self, request_id: int, approved: bool) -> None:
        status = "Approved" if approved else "Rejected"
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE approval_requests
                SET status = ?, decided_at = ?
                WHERE id = ? AND status = 'Proposed'
                """,
                (status, datetime.now(UTC).isoformat(), request_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Approval request was not found or was already decided")
            connection.execute(
                """
                UPDATE ministry_drafts SET status = ?, updated_at = ?
                WHERE approval_request_id = ?
                """,
                (MinistryDraftStatus.APPROVED.value if approved else MinistryDraftStatus.REJECTED.value,
                 datetime.now(UTC).isoformat(), request_id),
            )

    def list_approval_requests(self, limit: int = 50) -> list[ApprovalRequestRecord]:
        safe_limit = max(1, min(limit, 100))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, tool_name, action, target, payload_json, status,
                       requested_at, decided_at, executed_at, execution_status,
                       execution_detail
                FROM approval_requests
                ORDER BY requested_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [
            ApprovalRequestRecord(
                id=row["id"],
                tool_name=row["tool_name"],
                action=row["action"],
                target=row["target"],
                payload=json.loads(row["payload_json"]),
                status=row["status"],
                requested_at=row["requested_at"],
                decided_at=row["decided_at"],
                executed_at=row["executed_at"],
                execution_status=row["execution_status"],
                execution_detail=row["execution_detail"],
            )
            for row in rows
        ]

    def get_approval_request(self, request_id: int) -> ApprovalRequestRecord:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, tool_name, action, target, payload_json, status,
                       requested_at, decided_at, executed_at, execution_status,
                       execution_detail
                FROM approval_requests WHERE id = ?
                """,
                (request_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Approval request was not found")
        return ApprovalRequestRecord(
            id=row["id"], tool_name=row["tool_name"], action=row["action"],
            target=row["target"], payload=json.loads(row["payload_json"]),
            status=row["status"], requested_at=row["requested_at"],
            decided_at=row["decided_at"], executed_at=row["executed_at"],
            execution_status=row["execution_status"],
            execution_detail=row["execution_detail"],
        )

    def record_external_execution(
        self, request_id: int, success: bool, detail: str
    ) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE approval_requests
                SET executed_at = ?, execution_status = ?, execution_detail = ?
                WHERE id = ? AND status = 'Approved' AND executed_at IS NULL
                """,
                (
                    datetime.now(UTC).isoformat(),
                    "Succeeded" if success else "Failed",
                    detail[:1000],
                    request_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Action is not approved or was already executed")
            connection.execute(
                """
                UPDATE ministry_drafts SET status = ?, updated_at = ?
                WHERE approval_request_id = ?
                """,
                (MinistryDraftStatus.SENT.value if success else MinistryDraftStatus.FAILED.value,
                 datetime.now(UTC).isoformat(), request_id),
            )

    def create_ministry_draft(self, draft: NewMinistryDraft) -> int:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ministry_drafts
                    (workflow_type, title, destination, message, scheduled_for,
                     source_type, source_ref, source_timestamp, status,
                     approval_request_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    draft.workflow_type.value,
                    draft.title,
                    draft.destination,
                    draft.message,
                    draft.scheduled_for.isoformat() if draft.scheduled_for else None,
                    draft.source_type,
                    draft.source_ref,
                    draft.source_timestamp.isoformat() if draft.source_timestamp else None,
                    MinistryDraftStatus.DRAFT.value,
                    now,
                    now,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a ministry draft id")
            return cursor.lastrowid

    def link_ministry_approval(self, draft_id: int, approval_request_id: int) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE ministry_drafts
                SET approval_request_id = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (approval_request_id, MinistryDraftStatus.PROPOSED.value,
                 datetime.now(UTC).isoformat(), draft_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Ministry draft was not found")

    def list_ministry_drafts(self, limit: int = 50) -> list[MinistryDraft]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM ministry_drafts ORDER BY updated_at DESC LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [MinistryDraft.model_validate(dict(row)) for row in rows]

    def create_bible_material(self, material: NewBibleStudyMaterial) -> int:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO bible_study_materials
                    (title, passage, study_date, drive_url, storage_location,
                     status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (material.title, material.passage,
                 material.study_date.isoformat() if material.study_date else None,
                 material.drive_url, material.storage_location, material.status,
                 material.notes, now, now),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a Bible material id")
            return cursor.lastrowid

    def list_bible_materials(self, query: str = "") -> list[BibleStudyMaterial]:
        sql = "SELECT * FROM bible_study_materials"
        parameters: tuple[object, ...] = ()
        if query.strip():
            sql += " WHERE title LIKE ? OR passage LIKE ? OR notes LIKE ?"
            pattern = f"%{query.strip()}%"
            parameters = (pattern, pattern, pattern)
        sql += " ORDER BY COALESCE(study_date, '9999-12-31'), title"
        with self._connection() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [BibleStudyMaterial.model_validate(dict(row)) for row in rows]

    def create_task(self, task: NewHouseholdTask) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO household_tasks
                    (title, scope, owner, due_date, priority, status, source, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.title,
                    task.scope.value,
                    task.owner,
                    task.due_date.isoformat() if task.due_date else None,
                    task.priority.value,
                    TaskStatus.TODO.value,
                    task.source,
                    task.notes,
                    datetime.now(UTC).isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a task id")
            return cursor.lastrowid

    def list_tasks(self, include_done: bool = True) -> list[HouseholdTask]:
        query = """
            SELECT id, title, scope, owner, due_date, priority, status,
                   source, notes, created_at
            FROM household_tasks
        """
        parameters: tuple[object, ...] = ()
        if not include_done:
            query += " WHERE status != ?"
            parameters = (TaskStatus.DONE.value,)
        query += " ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, due_date, id"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [HouseholdTask.model_validate(dict(row)) for row in rows]

    def update_task_status(self, task_id: int, status: TaskStatus) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE household_tasks SET status = ? WHERE id = ?",
                (status.value, task_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Task was not found")

    def create_grocery_item(self, item: NewGroceryItem) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO grocery_items
                    (week_start, name, category, quantity, needed_for,
                     assigned_to, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.week_start.isoformat(),
                    item.name,
                    item.category,
                    item.quantity,
                    item.needed_for,
                    item.assigned_to,
                    GroceryStatus.NEEDED.value,
                    datetime.now(UTC).isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a grocery item id")
            return cursor.lastrowid

    def list_grocery_items(
        self, week_start: date, include_purchased: bool = True
    ) -> list[GroceryItem]:
        query = """
            SELECT id, week_start, name, category, quantity, needed_for,
                   assigned_to, status, created_at
            FROM grocery_items
            WHERE week_start = ?
        """
        parameters: list[object] = [week_start.isoformat()]
        if not include_purchased:
            query += " AND status != ?"
            parameters.append(GroceryStatus.PURCHASED.value)
        query += " ORDER BY category, name, id"
        with self._connection() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()
        return [GroceryItem.model_validate(dict(row)) for row in rows]

    def update_grocery_status(self, item_id: int, status: GroceryStatus) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE grocery_items SET status = ? WHERE id = ?",
                (status.value, item_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Grocery item was not found")

    def create_travel_plan(self, plan: NewTravelPlan) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO travel_plans
                    (title, depart_date, return_date, origin, destination,
                     travelers, transport_mode, lodging, confirmation_refs,
                     notes, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.title,
                    plan.depart_date.isoformat(),
                    plan.return_date.isoformat(),
                    plan.origin,
                    plan.destination,
                    plan.travelers,
                    plan.transport_mode,
                    plan.lodging,
                    plan.confirmation_refs,
                    plan.notes,
                    TripStatus.IDEA.value,
                    datetime.now(UTC).isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a travel plan id")
            return cursor.lastrowid

    def list_travel_plans(self, include_completed: bool = False) -> list[TravelPlan]:
        query = """
            SELECT id, title, depart_date, return_date, origin, destination,
                   travelers, transport_mode, lodging, confirmation_refs,
                   notes, status, created_at
            FROM travel_plans
        """
        parameters: tuple[object, ...] = ()
        if not include_completed:
            query += " WHERE status != ?"
            parameters = (TripStatus.COMPLETED.value,)
        query += " ORDER BY depart_date, id"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [TravelPlan.model_validate(dict(row)) for row in rows]

    def update_travel_status(self, plan_id: int, status: TripStatus) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE travel_plans SET status = ? WHERE id = ?",
                (status.value, plan_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Travel plan was not found")

    def save_capstone_run(
        self,
        request: CapstonePlanningRequest,
        brief: WeeklyBrief,
        trace: RunTrace,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO capstone_runs
                    (run_id, request_json, brief_json, trace_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    trace.run_id,
                    request.model_dump_json(),
                    brief.model_dump_json(),
                    trace.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def latest_capstone_run(
        self,
    ) -> tuple[CapstonePlanningRequest, WeeklyBrief, RunTrace] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT request_json, brief_json, trace_json
                FROM capstone_runs
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return (
            CapstonePlanningRequest.model_validate_json(row["request_json"]),
            WeeklyBrief.model_validate_json(row["brief_json"]),
            RunTrace.model_validate_json(row["trace_json"]),
        )

    def upsert_preference(
        self,
        key: str,
        value: str,
        owner: str,
        source: str,
        effective_date: date,
        sensitivity: str = "Household",
    ) -> None:
        confirmed_at = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO confirmed_preferences
                    (preference_key, value, owner, source, effective_date, sensitivity, confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(preference_key) DO UPDATE SET
                    value = excluded.value,
                    owner = excluded.owner,
                    source = excluded.source,
                    effective_date = excluded.effective_date,
                    sensitivity = excluded.sensitivity,
                    confirmed_at = excluded.confirmed_at
                """,
                (key, value, owner, source, effective_date.isoformat(), sensitivity, confirmed_at),
            )

    def list_preferences(self) -> list[ConfirmedPreference]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT preference_key AS key, value, owner, source,
                       effective_date, sensitivity, confirmed_at
                FROM confirmed_preferences
                ORDER BY preference_key
                """
            ).fetchall()
        return [ConfirmedPreference.model_validate(dict(row)) for row in rows]

    def save_evaluation_result(self, benchmark_name: str, result: dict[str, object]) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO evaluation_results (benchmark_name, result_json, created_at)
                VALUES (?, ?, ?)
                """,
                (benchmark_name, json.dumps(result), datetime.now(UTC).isoformat()),
            )
