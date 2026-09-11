from __future__ import annotations

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from householdos.domain.schedule import CalendarEvent, DaySchedule, EventCategory, ScheduleAnalysis
from householdos.workflows.operations import (
    answer_household_query,
    build_bible_cowork_reminder,
    build_event_one_pager,
    build_fellowship_reminder,
    build_pastor_event_announcement,
    extract_pastor_email,
)


class OperationsWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        timezone = ZoneInfo("America/Los_Angeles")
        self.event = CalendarEvent(
            id="event-1",
            source_id="test",
            person="Student A",
            title="Soccer training",
            start_at=datetime(2026, 9, 11, 17, 0, tzinfo=timezone),
            end_at=datetime(2026, 9, 11, 19, 0, tzinfo=timezone),
            category=EventCategory.SOCCER,
            location="Highland Middle School",
        )
        self.analysis = ScheduleAnalysis(
            week_start=date(2026, 9, 7),
            week_end=date(2026, 9, 13),
            days=[
                DaySchedule(
                    date=date(2026, 9, 7 + index),
                    events=[self.event] if index == 4 else [],
                )
                for index in range(7)
            ],
        )

    def test_offline_query_answers_by_weekday(self) -> None:
        response = answer_household_query("What is on Friday?", self.analysis, [])

        self.assertIn("Soccer training", response)
        self.assertIn("5:00 PM", response)

    def test_event_one_pager_contains_source_and_location(self) -> None:
        result = build_event_one_pager(self.event, self.analysis)

        self.assertIn("Highland Middle School", result.markdown)
        self.assertIn("**Source:** test", result.markdown)
        self.assertTrue(result.filename.endswith(".md"))

    def test_pastor_email_extraction_preserves_body_and_attribution(self) -> None:
        raw = "From: Pastor Lee <pastor@example.com>\nSubject: Weekly encouragement\n\nWalk in hope this week."

        result = extract_pastor_email(raw, "李牧師")

        self.assertEqual(result.subject, "Weekly encouragement")
        self.assertIn("Walk in hope this week.", result.line_message)
        self.assertTrue(result.line_message.endswith("— 李牧師"))

    def test_four_ministry_drafts_preserve_schedule_and_assignments(self) -> None:
        fellowship = build_fellowship_reminder(
            date(2026, 9, 18), "查經團契", "詩班房", "7:30 PM", "Zoom available"
        )
        self.assertIn("2026/09/18", fellowship)
        self.assertIn("7:15 PM", fellowship)

        bible_fellowship = build_fellowship_reminder(
            date(2026, 9, 18), "查經", "詩班房", "7:30 PM",
            "Zoom：https://example.test/private", meeting_mode="線下",
            zoom_link="https://example.test/private", bible_passage="約翰福音 11:1–16",
            leader="A", helpers=["B", "C"],
        )
        self.assertNotIn("Zoom", bible_fellowship)
        self.assertIn("查經章節：約翰福音 11:1–16", bible_fellowship)
        self.assertIn("帶領人：A", bible_fellowship)
        self.assertIn("協助同工：B、C", bible_fellowship)

        extracted = extract_pastor_email(
            "From: Pastor Lee\nSubject: Prayer\n\nPlease join us.", "李牧師"
        )
        prayer = build_pastor_event_announcement(extracted, "online_prayer", "週六 7:30 AM")
        forecast = build_pastor_event_announcement(extracted, "sunday_forecast", "主日 10:00 AM")
        self.assertIn("週六線上禱告會", prayer)
        self.assertIn("主日信息預告", forecast)

        cowork = build_bible_cowork_reminder(
            date(2026, 10, 2), "約翰福音 3", "A", "B", "C", "https://docs.google.com/x"
        )
        self.assertIn("帶領：A", cowork)
        self.assertIn("協助：B、C", cowork)


if __name__ == "__main__":
    unittest.main()
