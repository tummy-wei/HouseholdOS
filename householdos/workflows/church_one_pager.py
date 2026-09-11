"""Build compact public or admin church schedules from spreadsheet rows."""

from __future__ import annotations

from datetime import date, datetime


def _parse_date(value: str) -> date | None:
    for date_format in ("%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), date_format).date()
        except ValueError:
            continue
    return None


def _escape_markdown(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def build_church_one_pager(
    public_events: list[dict[str, str]],
    helper_events: list[dict[str, str]],
    *,
    include_private: bool,
    include_cancelled: bool = False,
) -> tuple[list[dict[str, str]], str]:
    """Deduplicate matched rows and return display rows plus Markdown."""
    public_by_id = {item.get("event_id", ""): item for item in public_events}
    helpers_by_id = {item.get("event_id", ""): item for item in helper_events}
    event_ids = list(public_by_id)
    if include_private:
        event_ids.extend(event_id for event_id in helpers_by_id if event_id not in public_by_id)

    rows: list[dict[str, str]] = []
    for event_id in event_ids:
        public = public_by_id.get(event_id, {})
        helper = helpers_by_id.get(event_id, {})
        source = public or helper
        event_date = _parse_date(source.get("date", ""))
        if not event_date:
            continue
        status = source.get("status", "") or helper.get("status", "")
        if not include_cancelled and status in {"已取消", "取消"}:
            continue
        row = {
            "Date": event_date.strftime("%Y-%m-%d"),
            "Time": "–".join(
                value for value in [source.get("start_time", ""), source.get("end_time", "")] if value
            ) or "All day",
            "Event": source.get("title", "") or helper.get("title", "") or "Untitled",
            "Location": source.get("location", "") or helper.get("location", "") or "待確認",
            "Status": status or "—",
        }
        if include_private:
            row.update({
                "Type": helper.get("activity_type", "") or "—",
                "Passage": helper.get("bible_passage", "") or "—",
                "Leader": helper.get("leader", "") or "—",
                "Helpers": "、".join(
                    value for value in [helper.get("helper_one", ""), helper.get("helper_two", "")] if value
                ) or "—",
                "Preparation": helper.get("preparation_reminder", "") or "—",
            })
        rows.append(row)

    rows.sort(key=lambda item: (item["Date"], item["Time"], item["Event"]))
    title = "# S&L 26H2 church schedule — Admin" if include_private else "# S&L 26H2 church schedule — Public"
    if not rows:
        return rows, f"{title}\n\nNo events are available.\n"
    columns = list(rows[0])
    markdown_lines = [
        title,
        "",
        f"Events: {len(rows)}",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    markdown_lines.extend(
        "| " + " | ".join(_escape_markdown(row[column]) for column in columns) + " |"
        for row in rows
    )
    return rows, "\n".join(markdown_lines) + "\n"
