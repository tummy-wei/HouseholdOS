from __future__ import annotations

import unittest

from householdos.workflows.church_one_pager import build_church_one_pager


class ChurchOnePagerTests(unittest.TestCase):
    def test_public_deduplicates_and_hides_private_assignments(self) -> None:
        public = [{
            "event_id": "CH-1", "date": "9/18/2026", "title": "查經",
            "start_time": "7:30 PM", "end_time": "9:00 PM", "location": "詩班房",
            "status": "已確認",
        }]
        helpers = [{
            "event_id": "CH-1", "date": "9/18/2026", "title": "查經",
            "leader": "Leader", "helper_one": "One", "helper_two": "Two",
            "activity_type": "查經", "bible_passage": "John 1",
        }]

        rows, markdown = build_church_one_pager(
            public, helpers, include_private=False
        )

        self.assertEqual(len(rows), 1)
        self.assertNotIn("Leader", rows[0])
        self.assertNotIn("Leader", markdown)

    def test_admin_includes_helper_only_events_and_assignments(self) -> None:
        helpers = [{
            "event_id": "CH-2", "date": "11/8/2026", "title": "飯食服務",
            "leader": "Leader", "helper_one": "One", "helper_two": "Two",
            "activity_type": "服務",
        }]

        rows, _ = build_church_one_pager([], helpers, include_private=True)

        self.assertEqual(rows[0]["Event"], "飯食服務")
        self.assertEqual(rows[0]["Helpers"], "One、Two")
