from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from householdos.config import Settings
from householdos.domain.models import ApprovalRequestRecord
from householdos.infrastructure.external_actions import adapter_readiness, execute_approved_action


class ExternalActionTests(unittest.TestCase):
    def test_adapters_fail_closed_when_credentials_are_absent(self) -> None:
        readiness = adapter_readiness(Settings(openai_api_key=None))
        self.assertFalse(readiness["line.send"])
        self.assertFalse(readiness["line.send.bible"])
        self.assertFalse(readiness["line.send.helpers"])
        self.assertFalse(readiness["google_apps_script.update_and_sync"])

    def test_helpers_destination_can_be_ready_independently(self) -> None:
        readiness = adapter_readiness(Settings(
            openai_api_key=None,
            line_channel_access_token="token",
            line_helpers_group_id="helpers-group",
        ))
        self.assertTrue(readiness["line.send"])
        self.assertTrue(readiness["line.send.helpers"])
        self.assertFalse(readiness["line.send.bible"])

    def test_execution_rejects_unapproved_request(self) -> None:
        request = ApprovalRequestRecord(
            id=1, tool_name="line.send", action="Send", target="Group",
            payload={"message": "Test"}, status="Proposed", requested_at="now",
        )
        with self.assertRaises(PermissionError):
            execute_approved_action(request, Settings(openai_api_key=None))

    def test_execution_rejects_approved_action_before_scheduled_time(self) -> None:
        request = ApprovalRequestRecord(
            id=2, tool_name="line.send", action="Send", target="Group",
            payload={
                "message": "Test",
                "scheduled_for": (datetime.now() + timedelta(days=1)).isoformat(),
            },
            status="Approved", requested_at="now",
        )
        with self.assertRaisesRegex(PermissionError, "scheduled"):
            execute_approved_action(request, Settings(openai_api_key=None))
