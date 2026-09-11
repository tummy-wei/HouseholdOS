"""Read-only Gmail intake for tightly scoped pastor-message rules."""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@dataclass(frozen=True)
class GmailIntakeRule:
    key: str
    account_email: str
    token_file: Path
    query: str
    subject_prefixes: tuple[str, ...]
    expected_sender: str = "pastor@example.org"


@dataclass(frozen=True)
class GmailMessageResult:
    success: bool
    detail: str
    message_id: str = ""
    raw_email: str = ""
    subject: str = ""
    sender: str = ""
    received_at: datetime | None = None


def token_is_configured(token_file: Path) -> bool:
    return token_file.is_file()


def readable_email_source(raw_bytes: bytes) -> str:
    """Decode an RFC email into readable headers and its preferred text body."""
    parsed = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    body_part = (
        parsed.get_body(preferencelist=("plain", "html"))
        if parsed.is_multipart()
        else parsed
    )
    body = str(body_part.get_content()).strip() if body_part else ""
    if body_part and body_part.get_content_type() == "text/html":
        body = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", body, flags=re.I | re.S)
        body = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", body, flags=re.I)
        body = html.unescape(re.sub(r"<[^>]+>", " ", body))
        body = "\n".join(line.strip() for line in body.splitlines() if line.strip())
    headers = [
        f"From: {str(parsed.get('from') or '').strip()}",
        f"Subject: {str(parsed.get('subject') or '').strip()}",
        f"Date: {str(parsed.get('date') or '').strip()}",
    ]
    return "\n".join(headers) + "\n\n" + body


def latest_matching_message(rule: GmailIntakeRule) -> GmailMessageResult:
    """Return the newest verified match without modifying the mailbox."""
    if not rule.token_file.is_file():
        return GmailMessageResult(False, f"OAuth authorization is missing for {rule.account_email}")
    try:
        credentials = Credentials.from_authorized_user_file(
            str(rule.token_file), [GMAIL_READONLY_SCOPE]
        )
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            rule.token_file.write_text(credentials.to_json(), encoding="utf-8")
        if not credentials.valid:
            return GmailMessageResult(False, f"OAuth authorization expired for {rule.account_email}")

        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        actual_account = str(profile.get("emailAddress", "")).lower()
        if actual_account != rule.account_email.lower():
            return GmailMessageResult(
                False,
                f"Token account mismatch: expected {rule.account_email}, got {actual_account or 'unknown'}",
            )

        listing = service.users().messages().list(
            userId="me", q=rule.query, maxResults=10
        ).execute()
        for item in listing.get("messages", []):
            gmail_message = service.users().messages().get(
                userId="me", id=item["id"], format="raw"
            ).execute()
            encoded = gmail_message.get("raw", "")
            raw_bytes = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            parsed = BytesParser(policy=policy.default).parsebytes(raw_bytes)
            subject = str(parsed.get("subject") or "").strip()
            sender = parseaddr(str(parsed.get("from") or ""))[1].lower()
            if sender != rule.expected_sender.lower():
                continue
            if not any(subject.startswith(prefix) for prefix in rule.subject_prefixes):
                continue
            received_at = datetime.fromtimestamp(int(gmail_message["internalDate"]) / 1000)
            return GmailMessageResult(
                True,
                f"Found matching message in {rule.account_email}",
                message_id=str(item["id"]),
                raw_email=readable_email_source(raw_bytes),
                subject=subject,
                sender=sender,
                received_at=received_at,
            )
        return GmailMessageResult(False, f"No matching recent message in {rule.account_email}")
    except (OSError, ValueError, HttpError) as error:
        return GmailMessageResult(False, f"Gmail intake failed for {rule.account_email}: {error}")
