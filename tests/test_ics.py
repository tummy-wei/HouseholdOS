from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from householdos.domain.schedule import EventCategory
from householdos.infrastructure.ics import ICSCalendarSource


class ICSCalendarSourceTests(unittest.TestCase):
    def test_repairs_nonpositive_upstream_event_duration(self) -> None:
        content = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:bad-duration
DTSTART:20260908T190000
DTEND:20260908T190000
SUMMARY:Soccer training
END:VEVENT
END:VCALENDAR
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.ics"
            path.write_text(content, encoding="utf-8")
            source = ICSCalendarSource(path, "soccer", "Student A", EventCategory.SOCCER)

            event = source.events_between(date(2026, 9, 8), date(2026, 9, 8))[0]

        self.assertEqual((event.end_at - event.start_at).total_seconds(), 3600)

    def test_reads_utc_and_all_day_events_in_household_timezone(self) -> None:
        content = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:timed-1
DTSTART:20260908T000000Z
DTEND:20260908T020000Z
SUMMARY:Training
LOCATION:Highland MS
END:VEVENT
BEGIN:VEVENT
UID:day-1
DTSTART;VALUE=DATE:20260908
SUMMARY:Dress uniform
END:VEVENT
END:VCALENDAR
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calendar.ics"
            path.write_text(content, encoding="utf-8")
            source = ICSCalendarSource(
                path, "soccer", "Student A", EventCategory.SOCCER
            )

            events = source.events_between(date(2026, 9, 7), date(2026, 9, 13))

        self.assertEqual(len(events), 2)
        timed = next(event for event in events if not event.all_day)
        self.assertEqual(timed.start_at.hour, 17)
        self.assertEqual(timed.start_at.date(), date(2026, 9, 7))
        self.assertEqual(timed.location, "Highland MS")
        self.assertTrue(any(event.all_day for event in events))


if __name__ == "__main__":
    unittest.main()
