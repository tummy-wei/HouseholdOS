from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from householdos.domain.operations import (
    GroceryStatus,
    NewGroceryItem,
    NewHouseholdTask,
    NewTravelPlan,
    TaskPriority,
    TaskScope,
    TaskStatus,
    TripStatus,
)
from householdos.infrastructure.sqlite import SQLitePlanRepository


class FiveDomainPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLitePlanRepository(Path(self.directory.name) / "test.db")
        self.repository.initialize()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_grocery_list_is_week_scoped_and_actionable(self) -> None:
        item_id = self.repository.create_grocery_item(
            NewGroceryItem(
                week_start=date(2026, 9, 7),
                name="Milk",
                category="Dairy",
                quantity="2 gallons",
                needed_for="School lunches",
                assigned_to="Parent B",
            )
        )
        items = self.repository.list_grocery_items(date(2026, 9, 7), False)
        self.assertEqual([item.name for item in items], ["Milk"])
        self.repository.update_grocery_status(item_id, GroceryStatus.PURCHASED)
        self.assertEqual(self.repository.list_grocery_items(date(2026, 9, 7), False), [])

    def test_travel_plan_progresses_through_explicit_states(self) -> None:
        plan_id = self.repository.create_travel_plan(
            NewTravelPlan(
                title="Portland weekend",
                depart_date=date(2026, 10, 2),
                return_date=date(2026, 10, 4),
                origin="Bellevue",
                destination="Portland",
                travelers="Family",
                transport_mode="Car",
            )
        )
        self.repository.update_travel_status(plan_id, TripStatus.CONFIRMED)
        self.assertEqual(self.repository.list_travel_plans()[0].status, TripStatus.CONFIRMED)

    def test_maintenance_uses_the_shared_task_lifecycle(self) -> None:
        task_id = self.repository.create_task(
            NewHouseholdTask(
                title="Replace furnace filter",
                scope=TaskScope.MAINTENANCE,
                owner="Parent A",
                due_date=date(2026, 9, 12),
                priority=TaskPriority.HIGH,
            )
        )
        task = next(item for item in self.repository.list_tasks() if item.id == task_id)
        self.assertEqual(task.scope, TaskScope.MAINTENANCE)
        self.repository.update_task_status(task_id, TaskStatus.DONE)
        completed = next(item for item in self.repository.list_tasks() if item.id == task_id)
        self.assertEqual(completed.status, TaskStatus.DONE)


if __name__ == "__main__":
    unittest.main()
