from __future__ import annotations

import unittest
from email.message import EmailMessage
from pathlib import Path

from householdos.infrastructure.gmail_inbox import (
    GmailIntakeRule,
    latest_matching_message,
    readable_email_source,
)


class GmailInboxTests(unittest.TestCase):
    def test_base64_mime_body_is_made_readable(self) -> None:
        message = EmailMessage()
        message["From"] = "Example Pastor <pastor@example.org>"
        message["Subject"] = "國語牧函 - 測試"
        message["Date"] = "Sun, 6 Sep 2026 08:00:00 -0700"
        message.set_content("弟兄姊妹平安，這是本週信息。", cte="base64")

        readable = readable_email_source(message.as_bytes())

        self.assertIn("Subject: 國語牧函 - 測試", readable)
        self.assertIn("弟兄姊妹平安，這是本週信息。", readable)
        self.assertNotIn("Content-Transfer-Encoding", readable)

    def test_missing_oauth_token_fails_closed_without_network_access(self) -> None:
        rule = GmailIntakeRule(
            key="church-prayer",
            account_email="church-account@example.com",
            token_file=Path("/definitely/missing/gmail-token.json"),
            query='from:pastor@example.org subject:"請小組長轉發"',
            subject_prefixes=("[red-mandarin-prayer] 請小組長轉發：",),
        )

        result = latest_matching_message(rule)

        self.assertFalse(result.success)
        self.assertIn("OAuth authorization is missing", result.detail)


if __name__ == "__main__":
    unittest.main()
