from __future__ import annotations

import unittest
from datetime import date, time

from householdos.domain.schedule import RecurringActivity, ScheduleException
from householdos.workflows.schedule_analysis import ScheduleAnalysisWorkflow


def activity(
    activity_id: str,
    person: str,
    title: str,
    weekday: int,
    start: time,
    end: time,
    location: str = "Away",
) -> RecurringActivity:
    return RecurringActivity(
        activity_id=activity_id,
        person=person,
        title=title,
        weekday=weekday,
        start_time=start,
        end_time=end,
        location=location,
        arrival_buffer_min=15,
        driver="Assign weekly",
    )


class ScheduleAnalysisWorkflowTests(unittest.TestCase):
    def test_detects_same_person_overlap_and_open_driver(self) -> None:
        activities = [
            activity("one", "Student A", "Piano", 0, time(18), time(19)),
            activity("two", "Student A", "Math", 0, time(18, 30), time(20)),
        ]

        result = ScheduleAnalysisWorkflow().run(
            date(2026, 9, 7), [], activities
        )

        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(len(result.transportation), 2)
        self.assertTrue(all(not need.resolved for need in result.transportation))
        self.assertTrue(
            any("driver assignment" in item for item in result.missing_information)
        )

    def test_date_exception_changes_driver_and_time(self) -> None:
        activities = [
            activity("piano", "Student A", "Piano", 0, time(18), time(19))
        ]
        exception = ScheduleException(
            activity_id="piano",
            event_date=date(2026, 9, 7),
            new_start_time=time(19),
            new_end_time=time(20),
            driver="Parent B",
        )

        result = ScheduleAnalysisWorkflow().run(
            date(2026, 9, 7), [], activities, [exception]
        )

        event = result.days[0].events[0]
        self.assertEqual(event.start_at.hour, 19)
        self.assertEqual(result.transportation[0].driver, "Parent B")
        self.assertTrue(result.transportation[0].resolved)

    def test_cancelled_exception_removes_occurrence(self) -> None:
        activities = [
            activity("piano", "Student A", "Piano", 0, time(18), time(19))
        ]
        exception = ScheduleException(
            activity_id="piano",
            event_date=date(2026, 9, 7),
            cancelled=True,
        )

        result = ScheduleAnalysisWorkflow().run(
            date(2026, 9, 7), [], activities, [exception]
        )

        self.assertEqual(result.days[0].events, [])


if __name__ == "__main__":
    unittest.main()
