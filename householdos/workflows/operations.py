"""Deterministic operational workflows that remain useful without an LLM."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from email import policy
from email.parser import Parser

from householdos.domain.operations import EventOnePager, HouseholdTask, PastorMessageDraft
from householdos.domain.schedule import CalendarEvent, ScheduleAnalysis


def answer_household_query(
    query: str, analysis: ScheduleAnalysis, tasks: list[HouseholdTask]
) -> str:
    """Provide a grounded offline answer for common schedule and task questions."""
    lowered = query.casefold()
    if any(word in lowered for word in ("conflict", "overlap", "衝突", "冲突")):
        if not analysis.conflicts:
            return "I found no same-person overlaps in the selected week."
        return "\n".join(f"- {item.message}" for item in analysis.conflicts)

    if any(word in lowered for word in ("driver", "drive", "接送", "司機", "司机")):
        open_items = [item for item in analysis.transportation if not item.resolved]
        if not open_items:
            return "All detected transportation needs have a driver assigned."
        lines = [f"There are {len(open_items)} open driver assignments:"]
        lines.extend(
            f"- {item.event_start.strftime('%a %-I:%M %p')}: "
            f"{item.person} — {item.event_title}"
            for item in open_items[:12]
        )
        if len(open_items) > 12:
            lines.append(f"- …and {len(open_items) - 12} more.")
        return "\n".join(lines)

    if any(word in lowered for word in ("task", "todo", "to do", "church", "教會", "教会")):
        filtered = [task for task in tasks if task.status.value != "Done"]
        if "church" in lowered or "教會" in lowered or "教会" in lowered:
            filtered = [task for task in filtered if task.scope.value == "Church"]
        if not filtered:
            return "There are no open matching tasks."
        return "\n".join(
            f"- {task.title} — {task.owner}"
            + (f", due {task.due_date.isoformat()}" if task.due_date else "")
            for task in filtered[:15]
        )

    weekday_names = {
        "monday": 0, "星期一": 0,
        "tuesday": 1, "星期二": 1,
        "wednesday": 2, "星期三": 2,
        "thursday": 3, "星期四": 3,
        "friday": 4, "星期五": 4,
        "saturday": 5, "星期六": 5,
        "sunday": 6, "星期日": 6, "星期天": 6,
    }
    requested_day = next((index for name, index in weekday_names.items() if name in lowered), None)
    if requested_day is not None:
        day = analysis.days[requested_day]
        if not day.events:
            return f"There are no events on {day.date.strftime('%A, %B %-d')}."
        return "\n".join(
            [f"Events on {day.date.strftime('%A, %B %-d')}:"]
            + [
                f"- {'All day' if event.all_day else event.start_at.strftime('%-I:%M %p')}: "
                f"{event.person} — {event.title}"
                for event in day.events
            ]
        )

    event_count = sum(len(day.events) for day in analysis.days)
    open_tasks = sum(task.status.value != "Done" for task in tasks)
    return (
        f"For {analysis.week_start.isoformat()} through {analysis.week_end.isoformat()}, "
        f"I found {event_count} events, {len(analysis.conflicts)} hard conflict(s), "
        f"{sum(not item.resolved for item in analysis.transportation)} open driver assignment(s), "
        f"and {open_tasks} open task(s). Ask about a day, conflicts, drivers, or church tasks."
    )


def build_event_one_pager(
    event: CalendarEvent, analysis: ScheduleAnalysis
) -> EventOnePager:
    conflicts = [item.message for item in analysis.conflicts if event.id in item.event_ids]
    transport = next((item for item in analysis.transportation if item.event_id == event.id), None)
    preparation = event.description.strip() or "Confirm materials, clothing, and any required forms."
    time_text = "All day" if event.all_day else (
        f"{event.start_at.strftime('%-I:%M %p')}–{event.end_at.strftime('%-I:%M %p')}"
    )
    transportation = "Not required or not identified."
    if transport:
        departure = transport.depart_by.strftime("%-I:%M %p") if transport.depart_by else "Pending travel time"
        transportation = (
            f"Driver: {transport.driver}; arrive by {transport.arrive_by.strftime('%-I:%M %p')}; "
            f"depart by {departure}."
        )
    issue_lines = "\n".join(f"- {item}" for item in conflicts) or "- No direct event conflict detected."
    markdown = f"""# {event.title}

## At a glance

- **Date:** {event.start_at.strftime('%A, %B %-d, %Y')}
- **Time:** {time_text}
- **For:** {event.person}
- **Location:** {event.location or 'To be confirmed'}
- **Category:** {event.category.value}
- **Source:** {event.source_id}

## Purpose and source notes

{preparation}

## Preparation checklist

- Confirm attendance and event details.
- Prepare required materials or equipment.
- Confirm transportation and departure time.
- Check for a same-day schedule change before leaving.

## Transportation

{transportation}

## Risks and open decisions

{issue_lines}
"""
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", event.title).strip("-").lower() or "event"
    return EventOnePager(
        event_id=event.id,
        title=event.title,
        event_date=event.start_at.date(),
        markdown=markdown,
        filename=f"{event.start_at.date().isoformat()}-{safe_name}.md",
        generated_at=datetime.now(UTC),
    )


def extract_pastor_email(raw_email: str, pastor_name: str = "牧師") -> PastorMessageDraft:
    """Extract an email conservatively and create a reviewable Traditional Chinese LINE draft."""
    message = Parser(policy=policy.default).parsestr(raw_email)
    subject = str(message.get("subject") or "本週牧者信息").strip()
    sender = str(message.get("from") or pastor_name).strip()
    if message.is_multipart():
        body_part = message.get_body(preferencelist=("plain",))
        body = body_part.get_content() if body_part else ""
    else:
        body = message.get_content() if message.get_payload() else raw_email
    body = str(body).strip()
    warnings: list[str] = []
    if not body:
        warnings.append("Email body is empty; do not send until the source is confirmed.")
    if sender == pastor_name:
        warnings.append("Sender was not found in the email headers; confirm attribution.")
    line_message = (
        "弟兄姊妹平安，\n\n"
        "以下是牧師本週的信息：\n\n"
        f"【{subject}】\n"
        f"{body}\n\n"
        f"— {pastor_name}"
    ).strip()
    return PastorMessageDraft(
        subject=subject,
        sender=sender,
        pastor_name=pastor_name,
        original_body=body,
        line_message=line_message,
        warnings=warnings,
    )


def build_fellowship_reminder(
    event_date: date,
    topic: str,
    location: str,
    start_time: str,
    notes: str = "",
    meeting_mode: str = "線下",
    zoom_link: str = "",
    bible_passage: str = "",
    leader: str = "",
    helpers: list[str] | None = None,
) -> str:
    normalized_mode = meeting_mode.casefold()
    is_online = any(
        marker in normalized_mode for marker in ("線上", "线上", "online", "zoom", "混合", "hybrid")
    )
    cleaned_notes = "\n".join(
        line for line in notes.splitlines()
        if is_online or "zoom" not in line.casefold()
    ).strip()
    detail_lines = [
        f"活動：{topic or '待確認'}",
        f"日期：{event_date.strftime('%Y/%m/%d')}",
        f"時間：{start_time}",
        f"聚會方式：{meeting_mode or '線下'}",
    ]
    if location:
        detail_lines.append(f"地點：{location}")
    if bible_passage:
        helper_names = [name for name in (helpers or []) if name]
        detail_lines.extend([
            f"查經章節：{bible_passage}",
            f"帶領人：{leader or '待確認'}",
            f"協助同工：{'、'.join(helper_names) if helper_names else '待確認'}",
        ])
    if not is_online:
        detail_lines.append("建議：7:15 PM 抵達，參加全教會敬拜及接送 AWANA。")
    if is_online and zoom_link:
        detail_lines.append(f"Zoom：{zoom_link}")
    detail_lines.append(
        f"備註：{cleaned_notes or '誠摯邀請大家預留時間，一起享受美好的團契。'}"
    )
    return (
        "親愛的弟兄姊妹，平安！\n"
        "願大家這週都在主裡平安、喜樂。溫馨提醒本週五的團契安排：\n\n"
        + "\n".join(detail_lines)
        + "\n\n"
        "期待週五與大家見面！願主賜福。"
    )


def build_pastor_event_announcement(
    extracted: PastorMessageDraft, kind: str, event_details: str
) -> str:
    heading = "週六線上禱告會" if kind == "online_prayer" else "主日信息預告"
    return (
        f"弟兄姊妹平安，以下是本週{heading}：\n\n"
        f"【{extracted.subject}】\n"
        f"{event_details.strip()}\n\n"
        f"{extracted.original_body}\n\n"
        f"— {extracted.pastor_name}"
    ).strip()


def build_bible_cowork_reminder(
    study_date: date,
    passage: str,
    leader: str,
    helper_one: str,
    helper_two: str,
    material_url: str = "",
) -> str:
    reminder_date = study_date - timedelta(days=10, hours=12)
    material_line = material_url or "待補"
    return (
        "同工平安，提醒預備下一次查經：\n\n"
        f"查經日期：{study_date.strftime('%Y/%m/%d')}\n"
        f"經文：{passage or '待確認'}\n"
        f"帶領：{leader or '待確認'}\n"
        f"協助：{helper_one or '待確認'}、{helper_two or '待確認'}\n"
        f"預備材料：{material_line}\n"
        f"預備提醒基準：{reminder_date.strftime('%Y/%m/%d %I:%M %p')}（提前 1.5 週）\n\n"
        "請確認分工及材料；如需調整，請在群組回覆。"
    )


def build_event_line_announcement(event: CalendarEvent) -> str:
    time_text = "全日" if event.all_day else (
        f"{event.start_at.strftime('%Y/%m/%d（%a）%-I:%M %p')}–{event.end_at.strftime('%-I:%M %p')}"
    )
    return (
        "弟兄姊妹平安，提醒大家以下聚會安排：\n\n"
        f"主題：{event.title}\n"
        f"時間：{time_text}\n"
        f"地點：{event.location or '待確認'}\n\n"
        "請大家預留時間參加。如有變動，將另行通知。"
    )
