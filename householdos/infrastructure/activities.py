"""Editable JSON-backed recurring activities for the local-first MVP."""

from __future__ import annotations

import json
from pathlib import Path

from householdos.domain.schedule import RecurringActivity


class JSONRecurringActivitySource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def list_activities(self) -> list[RecurringActivity]:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [RecurringActivity.model_validate(item) for item in payload]

