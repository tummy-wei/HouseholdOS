from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from householdos.domain.models import DailyPlan, WeeklyPlan, WeeklyPlanningRequest
from householdos.infrastructure.sqlite import SQLitePlanRepository
from householdos.domain.schedule import ScheduleException
from householdos.domain.operations import (
    MinistryWorkflowType,
    NewBibleStudyMaterial,
    NewHouseholdTask,
    NewMinistryDraft,
    TaskPriority,
    TaskScope,
    TaskStatus,
)
from householdos.workflows.weekly_planning import WeeklyPlanningWorkflow


def sample_request() -> WeeklyPlanningRequest:
    return WeeklyPlanningRequest(
        week_start=date(2026, 7, 20),
        priorities=["Have three family dinners"],
        commitments=["Tuesday 6pm — swim practice"],
        constraints=["Keep Sunday light"],
    )


def sample_plan() -> WeeklyPlan:
    start = date(2026, 7, 20)
    return WeeklyPlan(
        title="A balanced week",
        summary="Protect commitments and keep enough slack for surprises.",
        days=[
            DailyPlan(date=start + timedelta(days=index), theme="Steady", tasks=[])
            for index in range(7)
        ],
        open_questions=[],
    )


class FakePlanner:
    def create_plan(self, request: WeeklyPlanningRequest) -> WeeklyPlan:
        return sample_plan()


class WrongWeekPlanner:
    def create_plan(self, request: WeeklyPlanningRequest) -> WeeklyPlan:
        plan = sample_plan()
        for day in plan.days:
            day.date += timedelta(days=7)
        return plan


class WeeklyPlanningWorkflowTests(unittest.TestCase):
    def test_workflow_persists_generated_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLitePlanRepository(Path(directory) / "test.db")
            repository.initialize()
            workflow = WeeklyPlanningWorkflow(FakePlanner(), repository)

            result = workflow.run(sample_request())

            self.assertEqual(result.title, "A balanced week")
            recent = repository.list_recent()
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0].week_start, date(2026, 7, 20))

    def test_plan_requires_seven_unique_ordered_days(self) -> None:
        plan_data = sample_plan().model_dump()
        plan_data["days"][1]["date"] = plan_data["days"][0]["date"]

        with self.assertRaises(ValueError):
            WeeklyPlan.model_validate(plan_data)

    def test_workflow_rejects_a_plan_for_the_wrong_week(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLitePlanRepository(Path(directory) / "test.db")
            repository.initialize()
            workflow = WeeklyPlanningWorkflow(WrongWeekPlanner(), repository)

            with self.assertRaisesRegex(ValueError, "requested week"):
                workflow.run(sample_request())

            self.assertEqual(repository.list_recent(), [])

    def test_repository_persists_exceptions_and_approval_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLitePlanRepository(Path(directory) / "test.db")
            repository.initialize()
            exception = ScheduleException(
                activity_id="piano",
                event_date=date(2026, 7, 20),
                driver="Parent B",
            )
            repository.save_schedule_exception(exception)

            loaded = repository.list_schedule_exceptions(
                date(2026, 7, 20), date(2026, 7, 26)
            )
            self.assertEqual(loaded, [exception])

            approval_id = repository.propose_external_action(
                "calendar.update", "Update event", "Piano", {"driver": "Parent B"}
            )
            repository.decide_external_action(approval_id, approved=True)
            approvals = repository.list_approval_requests()
            self.assertEqual(approvals[0].status, "Approved")

    def test_repository_persists_and_updates_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLitePlanRepository(Path(directory) / "test.db")
            repository.initialize()
            task_id = repository.create_task(
                NewHouseholdTask(
                    title="Prepare fellowship reminder",
                    scope=TaskScope.CHURCH,
                    owner="Parent A",
                    due_date=date(2026, 7, 22),
                    priority=TaskPriority.HIGH,
                )
            )

            repository.update_task_status(task_id, TaskStatus.DONE)
            tasks = repository.list_tasks()

            self.assertEqual(tasks[0].status, TaskStatus.DONE)
            self.assertEqual(repository.list_tasks(include_done=False), [])

    def test_repository_persists_only_explicitly_confirmed_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLitePlanRepository(Path(directory) / "test.db")
            repository.initialize()
            self.assertEqual(repository.list_preferences(), [])

            repository.upsert_preference(
                "dietary.student_b",
                "Dairy-free",
                "Student B",
                "Explicit test confirmation",
                date(2026, 9, 7),
            )

            preferences = repository.list_preferences()
            self.assertEqual(len(preferences), 1)
            self.assertEqual(preferences[0].value, "Dairy-free")

    def test_repository_persists_ministry_drafts_materials_and_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLitePlanRepository(Path(directory) / "test.db")
            repository.initialize()
            draft_id = repository.create_ministry_draft(NewMinistryDraft(
                workflow_type=MinistryWorkflowType.BIBLE_COWORK_PREP,
                title="Prepare John 3", destination="Helpers LINE group",
                message="Please prepare", source_type="Spreadsheet",
            ))
            approval_id = repository.propose_external_action(
                "line.send", "Bible cowork preparation", "Helpers LINE group",
                {"message": "Please prepare", "destination_key": "helpers"},
            )
            repository.link_ministry_approval(draft_id, approval_id)
            repository.decide_external_action(approval_id, True)
            repository.record_external_execution(approval_id, True, "request-123")
            repository.create_bible_material(NewBibleStudyMaterial(
                title="John 3 guide", passage="John 3",
                drive_url="https://docs.google.com/document/d/example",
            ))

            self.assertEqual(repository.list_ministry_drafts()[0].status.value, "Sent")
            self.assertEqual(repository.list_approval_requests()[0].execution_status, "Succeeded")
            self.assertEqual(repository.list_bible_materials("John")[0].passage, "John 3")


if __name__ == "__main__":
    unittest.main()
