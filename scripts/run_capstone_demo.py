"""Launch an isolated, sanitized HouseholdOS instance for screen recording."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DB = ROOT / "data" / "capstone_demo.db"


def main() -> None:
    env = os.environ.copy()
    env.update({
        "HOUSEHOLDOS_DEMO_MODE": "true",
        "HOUSEHOLDOS_DB_PATH": str(DEMO_DB),
        "PYTHONPATH": str(ROOT),
        "OPENAI_API_KEY": "",
        "LINE_CHANNEL_ACCESS_TOKEN": "",
        "LINE_BIBLE_GROUP_ID": "",
        "LINE_HELPERS_GROUP_ID": "",
        "GOOGLE_APPS_SCRIPT_WEB_APP_URL": "",
        "GOOGLE_APPS_SCRIPT_SHARED_SECRET": "",
    })
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/seed_capstone_demo.py")],
        cwd=ROOT,
        env=env,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8502"],
        cwd=ROOT,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
