"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str = "gpt-5.6-sol"
    database_path: Path = Path("data/householdos.db")
    line_channel_access_token: str | None = None
    line_bible_group_id: str | None = None
    line_helpers_group_id: str | None = None
    apps_script_web_app_url: str | None = None
    apps_script_shared_secret: str | None = None
    bible_materials_folder_id: str | None = None
    gmail_oauth_client_secret_file: Path = Path("secrets/gmail_oauth_client.json")
    gmail_church_token_file: Path = Path("secrets/gmail_church_token.json")
    gmail_personal_token_file: Path = Path("secrets/gmail_personal_token.json")
    gmail_church_account: str = "church-account@example.com"
    gmail_personal_account: str = "personal-account@example.com"
    pastor_sender_email: str = "pastor@example.org"
    demo_mode: bool = False

    @property
    def has_api_key(self) -> bool:
        return bool(self.openai_api_key)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        load_dotenv(".env.local", override=True)
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-sol"),
            database_path=Path(
                os.getenv("HOUSEHOLDOS_DB_PATH", "data/householdos.db")
            ),
            line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
            line_bible_group_id=os.getenv("LINE_BIBLE_GROUP_ID"),
            line_helpers_group_id=os.getenv("LINE_HELPERS_GROUP_ID"),
            apps_script_web_app_url=os.getenv("GOOGLE_APPS_SCRIPT_WEB_APP_URL"),
            apps_script_shared_secret=os.getenv("GOOGLE_APPS_SCRIPT_SHARED_SECRET"),
            bible_materials_folder_id=os.getenv("BIBLE_MATERIALS_FOLDER_ID"),
            gmail_oauth_client_secret_file=Path(os.getenv(
                "GMAIL_OAUTH_CLIENT_SECRET_FILE", "secrets/gmail_oauth_client.json"
            )),
            gmail_church_token_file=Path(os.getenv(
                "GMAIL_CHURCH_TOKEN_FILE", "secrets/gmail_church_token.json"
            )),
            gmail_personal_token_file=Path(os.getenv(
                "GMAIL_PERSONAL_TOKEN_FILE", "secrets/gmail_personal_token.json"
            )),
            gmail_church_account=os.getenv("GMAIL_CHURCH_ACCOUNT", "church-account@example.com"),
            gmail_personal_account=os.getenv("GMAIL_PERSONAL_ACCOUNT", "personal-account@example.com"),
            pastor_sender_email=os.getenv("PASTOR_SENDER_EMAIL", "pastor@example.org"),
            demo_mode=os.getenv("HOUSEHOLDOS_DEMO_MODE", "").lower() in {"1", "true", "yes", "on"},
        )
