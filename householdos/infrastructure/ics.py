"""Small, dependency-free reader for the concrete VEVENTs in subscribed ICS feeds."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from householdos.domain.schedule import CalendarEvent, EventCategory


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _parse_datetime(raw_key: str, value: str, timezone: ZoneInfo) -> tuple[datetime, bool]:
    if "VALUE=DATE" in raw_key or (len(value) == 8 and "T" not in value):
        parsed = datetime.strptime(value[:8], "%Y%m%d").date()
        return datetime.combine(parsed, time.min, tzinfo=timezone), True
    if value.endswith("Z"):
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        return parsed.astimezone(timezone), False
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    return parsed.replace(tzinfo=timezone), False


class ICSCalendarSource:
    """Normalize a local ICS snapshot into timezone-aware calendar events."""

    def __init__(
        self,
        path: str | Path,
        source_id: str,
        person: str,
        category: EventCategory,
        timezone: str = "America/Los_Angeles",
    ) -> None:
        self.path = Path(path)
        self.source_id = source_id
        self.person = person
        self.category = category
        self.timezone = ZoneInfo(timezone)

    def events_between(self, start: date, end: date) -> list[CalendarEvent]:
        if end < start:
            raise ValueError("Calendar range end must not precede start")
        text = self.path.read_text(encoding="utf-8", errors="replace")
        records: list[dict[str, tuple[str, str]]] = []
        current: dict[str, tuple[str, str]] | None = None
        for line in _unfold(text):
            if line == "BEGIN:VEVENT":
                current = {}
            elif line == "END:VEVENT" and current is not None:
                records.append(current)
                current = None
            elif current is not None and ":" in line:
                raw_key, value = line.split(":", 1)
                key = raw_key.split(";", 1)[0]
                current[key] = (raw_key, value)

        range_start = datetime.combine(start, time.min, tzinfo=self.timezone)
        range_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=self.timezone)
        events: list[CalendarEvent] = []
        for record in records:
            if "DTSTART" not in record:
                continue
            start_at, all_day = _parse_datetime(*record["DTSTART"], self.timezone)
            if "DTEND" in record:
                end_at, _ = _parse_datetime(*record["DTEND"], self.timezone)
            else:
                end_at = start_at + (timedelta(days=1) if all_day else timedelta(hours=1))
            if end_at <= start_at:
                end_at = start_at + (timedelta(days=1) if all_day else timedelta(hours=1))
            if end_at <= range_start or start_at >= range_end:
                continue
            uid = _unescape(record.get("UID", ("", f"{self.source_id}:{start_at.isoformat()}"))[1])
            events.append(
                CalendarEvent(
                    id=f"{self.source_id}:{uid}",
                    source_id=self.source_id,
                    person=self.person,
                    title=_unescape(record.get("SUMMARY", ("", "Untitled event"))[1]),
                    start_at=start_at,
                    end_at=end_at,
                    category=self.category,
                    location=_unescape(record.get("LOCATION", ("", ""))[1]),
                    description=_unescape(record.get("DESCRIPTION", ("", ""))[1]),
                    all_day=all_day,
                    authoritative=True,
                )
            )
        return sorted(events, key=lambda event: (event.start_at, event.title))
