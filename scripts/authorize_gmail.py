"""Authorize one HouseholdOS Gmail profile with read-only access."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from householdos.config import Settings
from householdos.infrastructure.gmail_inbox import GMAIL_READONLY_SCOPE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=("church", "personal"))
    args = parser.parse_args()
    settings = Settings.from_env()
    expected_email, token_file = (
        (settings.gmail_church_account, settings.gmail_church_token_file)
        if args.profile == "church"
        else (settings.gmail_personal_account, settings.gmail_personal_token_file)
    )
    client_file = settings.gmail_oauth_client_secret_file
    if not client_file.is_file():
        raise SystemExit(f"Missing OAuth desktop client file: {client_file}")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_file), [GMAIL_READONLY_SCOPE]
    )
    credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    actual_email = str(service.users().getProfile(userId="me").execute()["emailAddress"])
    if actual_email.lower() != expected_email.lower():
        raise SystemExit(f"Wrong account: expected {expected_email}, authorized {actual_email}")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Authorized read-only Gmail access for {actual_email}")


if __name__ == "__main__":
    main()
