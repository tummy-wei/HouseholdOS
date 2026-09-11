"""Add clearly labeled, idempotent demo records for the capstone presentation."""

from __future__ import annotations

from datetime import date, timedelta

from householdos.config import Settings
from householdos.domain.operations import (
    NewGroceryItem,
    NewHouseholdTask,
    NewTravelPlan,
    TaskPriority,
    TaskScope,
    TripStatus,
)
from householdos.infrastructure.sqlite import SQLitePlanRepository


DEMO_SOURCE = "Capstone demo data"


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def seed(repository: SQLitePlanRepository, today: date = date.today()) -> dict[str, int]:
    """Insert missing demo rows only and return counts created in this run."""
    repository.initialize()
    week_start = monday(today)
    created = {"groceries": 0, "travel": 0, "maintenance": 0}

    existing_groceries = {
        item.name for item in repository.list_grocery_items(week_start)
    }
    groceries = [
        NewGroceryItem(week_start=week_start, name="Bananas", category="Produce", quantity="8", needed_for="School lunches", assigned_to="Parent B"),
        NewGroceryItem(week_start=week_start, name="Baby spinach", category="Produce", quantity="1 large box", needed_for="Weeknight dinners", assigned_to="Parent A"),
        NewGroceryItem(week_start=week_start, name="Chicken thighs", category="Protein", quantity="3 lb", needed_for="Tuesday and Thursday dinners", assigned_to="Parent A"),
        NewGroceryItem(week_start=week_start, name="Greek yogurt", category="Dairy", quantity="2 tubs", needed_for="Breakfasts", assigned_to="Parent B"),
        NewGroceryItem(week_start=week_start, name="Whole wheat bread", category="Bakery", quantity="2 loaves", needed_for="School lunches", assigned_to="Parent B"),
        NewGroceryItem(week_start=week_start, name="Rice", category="Pantry", quantity="10 lb bag", needed_for="Household staple", assigned_to="Parent A"),
    ]
    for item in groceries:
        if item.name not in existing_groceries:
            repository.create_grocery_item(item)
            created["groceries"] += 1

    trip_title = "[DEMO] Portland family weekend"
    if trip_title not in {plan.title for plan in repository.list_travel_plans(True)}:
        trip_id = repository.create_travel_plan(NewTravelPlan(
            title=trip_title,
            depart_date=week_start + timedelta(days=39),
            return_date=week_start + timedelta(days=41),
            origin="Bellevue, WA",
            destination="Portland, OR",
            travelers="Parent A, Parent B, Student A, Student B",
            transport_mode="Car",
            lodging="Downtown Portland hotel - demo hold",
            confirmation_refs="Hotel DEMO-PDX-4821",
            notes="Demo record. Confirm soccer conflicts, reserve parking, and prepare a rainy-day option before booking.",
        ))
        repository.update_travel_status(trip_id, TripStatus.PLANNING)
        created["travel"] += 1

    existing_tasks = {task.title for task in repository.list_tasks(True)}
    maintenance = [
        NewHouseholdTask(title="[DEMO] Replace HVAC filter", scope=TaskScope.MAINTENANCE, owner="Parent A", due_date=week_start + timedelta(days=5), priority=TaskPriority.HIGH, source=DEMO_SOURCE, notes="Use 20 x 25 x 1 MERV 11 filter. Record completion for the 90-day cycle."),
        NewHouseholdTask(title="[DEMO] Test smoke and CO alarms", scope=TaskScope.MAINTENANCE, owner="Parent B", due_date=week_start + timedelta(days=12), priority=TaskPriority.MEDIUM, source=DEMO_SOURCE, notes="Test each floor and replace batteries that fail."),
        NewHouseholdTask(title="[DEMO] Schedule fall gutter cleaning", scope=TaskScope.MAINTENANCE, owner="Unassigned", due_date=week_start + timedelta(days=26), priority=TaskPriority.MEDIUM, source=DEMO_SOURCE, notes="Collect two quotes. HouseholdOS must not contact or book a contractor without approval."),
    ]
    for task in maintenance:
        if task.title not in existing_tasks:
            repository.create_task(task)
            created["maintenance"] += 1
    return created


if __name__ == "__main__":
    settings = Settings.from_env()
    result = seed(SQLitePlanRepository(settings.database_path))
    print("Capstone demo seed complete:", result)
