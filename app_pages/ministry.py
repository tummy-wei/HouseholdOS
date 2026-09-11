from __future__ import annotations

import calendar as month_calendar
from datetime import date, datetime, time, timedelta
from uuid import uuid4

import streamlit as st

from householdos.domain.operations import MinistryWorkflowType, NewBibleStudyMaterial, NewMinistryDraft
from householdos.infrastructure.external_actions import adapter_readiness, list_sheet_events
from householdos.infrastructure.gmail_inbox import (
    GmailIntakeRule,
    latest_matching_message,
    token_is_configured,
)
from householdos.ui.runtime import get_runtime
from householdos.workflows.operations import (
    build_bible_cowork_reminder,
    build_fellowship_reminder,
    build_pastor_event_announcement,
    extract_pastor_email,
)
from householdos.workflows.church_one_pager import build_church_one_pager

runtime = get_runtime()
readiness = adapter_readiness(runtime.settings)

if readiness["line.send.bible"] and readiness["line.send.helpers"]:
    line_status = "Ready"
elif readiness["line.send.helpers"]:
    line_status = "Helpers ready"
elif readiness["line.send.bible"]:
    line_status = "Bible group ready"
else:
    line_status = "Setup needed"
today = datetime.now().date()


def pastor_gmail_rule(output_kind: str) -> GmailIntakeRule:
    if output_kind == "Saturday online prayer":
        return GmailIntakeRule(
            key="church-prayer",
            account_email=runtime.settings.gmail_church_account,
            token_file=runtime.settings.gmail_church_token_file,
            query=f'from:{runtime.settings.pastor_sender_email} subject:"請小組長轉發" newer_than:30d',
            expected_sender=runtime.settings.pastor_sender_email,
            subject_prefixes=(
                "[red-mandarin-prayer] 請小組長轉發：",
                "[red-mandarin-prayer] 請小組長轉發:",
            ),
        )
    return GmailIntakeRule(
        key="personal-forecast",
        account_email=runtime.settings.gmail_personal_account,
        token_file=runtime.settings.gmail_personal_token_file,
        query=f'from:{runtime.settings.pastor_sender_email} subject:"國語牧函" newer_than:30d',
        expected_sender=runtime.settings.pastor_sender_email,
        subject_prefixes=("國語牧函 -", "國語牧函 –", "國語牧函-"),
    )


@st.cache_data(ttl="1m", max_entries=4, show_spinner=False)
def cached_latest_pastor_message(rule: GmailIntakeRule):
    return latest_matching_message(rule)


@st.fragment(run_every="5m")
def pastor_inbox_monitor(rule: GmailIntakeRule):
    if runtime.settings.demo_mode:
        st.info("Mailbox monitoring is disabled in capstone demo mode. Use synthetic pasted text for the demonstration.")
        return
    if not token_is_configured(rule.token_file):
        st.info(f"Connect {rule.account_email} to enable inbox monitoring.")
        return
    if st.button("Check inbox now", icon=":material/refresh:", key=f"gmail_refresh_{rule.key}"):
        cached_latest_pastor_message.clear()
    result = cached_latest_pastor_message(rule)
    if not result.success:
        st.warning(result.detail)
        return
    candidate_key = f"pastor_gmail_candidate_{rule.key}"
    previous = st.session_state.get(candidate_key)
    st.session_state[candidate_key] = result
    st.success(f"Inbox match: {result.subject}")
    st.caption(f"From {result.sender} · received {result.received_at.strftime('%Y-%m-%d %-I:%M %p')}")
    if not previous or previous.message_id != result.message_id:
        st.rerun(scope="app")


def next_weekday(weekday: int):
    days = (weekday - today.weekday()) % 7
    return today + timedelta(days=days or 7)


def parse_sheet_date(value: str) -> date | None:
    for date_format in ("%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_sheet_time(value: str, fallback: time) -> time:
    for time_format in ("%I:%M %p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), time_format).time()
        except (ValueError, AttributeError):
            continue
    return fallback


def queue_line_draft(*, workflow_type, title, destination, destination_key, message,
                     scheduled_for, source_type, source_ref="", source_timestamp=None):
    draft_id = runtime.repository.create_ministry_draft(NewMinistryDraft(
        workflow_type=workflow_type, title=title, destination=destination,
        message=message, scheduled_for=scheduled_for, source_type=source_type,
        source_ref=source_ref, source_timestamp=source_timestamp,
    ))
    approval_id = runtime.repository.propose_external_action(
        tool_name="line.send", action=workflow_type.value, target=destination,
        payload={"draft_id": draft_id, "destination_key": destination_key,
                 "message": message,
                 "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
                 "source_type": source_type, "source_ref": source_ref},
    )
    runtime.repository.link_ministry_approval(draft_id, approval_id)
    return approval_id


st.title("Ministry operations")
st.caption("Draft → preview → approve → send → verify. No outbound action skips review.")
drafts = runtime.repository.list_ministry_drafts()
approvals = runtime.repository.list_approval_requests()
with st.container(horizontal=True):
    st.metric("Saved ministry drafts", len(drafts), border=True)
    st.metric("Awaiting approval", sum(item.status == "Proposed" for item in approvals), border=True)
    st.metric("LINE adapter", line_status, border=True)
    st.metric("Calendar adapter", "Ready" if readiness["google_apps_script.update_and_sync"] else "Setup needed", border=True)

messages_tab, materials_tab, calendar_tab, history_tab = st.tabs(
    ["Message workflows", "Bible materials", "Calendar sync", "History"]
)

with messages_tab:
    workflow = st.segmented_control(
        "Workflow", ["Friday fellowship", "Pastor email", "Bible coworkers"],
        default="Friday fellowship",
    )
    if workflow == "Friday fellowship":
        st.subheader("Friday fellowship reminder")
        st.caption("The next Friday event is prefilled from the Public spreadsheet. Delivery is proposed for Wednesday and still requires review.")
        public_sheet = "26H2-Calendar-Public"
        public_events = st.session_state.get("church_calendar_events", {}).get(public_sheet, [])
        if not public_events and readiness["google_apps_script.update_and_sync"]:
            with st.spinner("Loading the next fellowship from the ministry calendar…"):
                source_result = list_sheet_events(runtime.settings, public_sheet)
            if source_result.success:
                event_cache = st.session_state.setdefault("church_calendar_events", {})
                event_cache[public_sheet] = source_result.events
                public_events = source_result.events
            else:
                st.warning(f"Calendar source could not be loaded: {source_result.detail}")
        helpers_sheet = "26H2-Calendar-Helpers"
        helpers_events = st.session_state.get("church_calendar_events", {}).get(helpers_sheet, [])
        if not helpers_events and readiness["google_apps_script.update_and_sync"]:
            helper_source_result = list_sheet_events(runtime.settings, helpers_sheet)
            if helper_source_result.success:
                event_cache = st.session_state.setdefault("church_calendar_events", {})
                event_cache[helpers_sheet] = helper_source_result.events
                helpers_events = helper_source_result.events

        next_friday = next_weekday(4)
        upcoming_fridays = sorted(
            [
                item for item in public_events
                if parse_sheet_date(item.get("date", ""))
                and parse_sheet_date(item.get("date", "")) >= next_friday
                and parse_sheet_date(item.get("date", "")).weekday() == 4
                and item.get("status") not in {"已取消", "取消"}
            ],
            key=lambda item: parse_sheet_date(item.get("date", "")),
        )
        fellowship_labels = {
            f"{item.get('date', '')} · {item.get('title', '')} · {item.get('status', '')}": item
            for item in upcoming_fridays
        }
        selected_fellowship_label = st.selectbox(
            "Fellowship source event", options=list(fellowship_labels),
            placeholder="No upcoming Friday event found",
        ) if fellowship_labels else None
        source_event = fellowship_labels.get(selected_fellowship_label, {})
        source_event_id = source_event.get("event_id", "manual")
        helper_event = next(
            (item for item in helpers_events if item.get("event_id") == source_event_id), {}
        )
        source_date = parse_sheet_date(source_event.get("date", "")) or next_friday
        source_start = parse_sheet_time(source_event.get("start_time", ""), time(19, 30))
        source_mode = source_event.get("meeting_mode") or helper_event.get("meeting_mode") or "線下"
        source_activity_type = helper_event.get("activity_type") or source_event.get("activity_type") or ""
        is_bible_study = "查經" in f"{source_activity_type} {source_event.get('title', '')}"
        source_passage = helper_event.get("bible_passage") or source_event.get("bible_passage") or ""
        mode_options = [source_mode] if source_mode not in {"線下", "線上", "混合"} else []
        mode_options.extend(["線下", "線上", "混合"])
        with st.form(f"fellowship_draft_form_{source_event_id}"):
            event_date = st.date_input("Fellowship date", value=source_date, key=f"fellowship_date_{source_event_id}")
            topic = st.text_input("Activity or topic", value=source_event.get("title", "待確認"), key=f"fellowship_topic_{source_event_id}")
            location = st.text_input("Location", value=source_event.get("location", "") or "詩班房", key=f"fellowship_location_{source_event_id}")
            start = st.time_input("Start time", value=source_start, key=f"fellowship_start_{source_event_id}")
            meeting_mode = st.selectbox("Meeting mode", mode_options, key=f"fellowship_mode_{source_event_id}")
            zoom_link = st.text_input(
                "Zoom link", value=source_event.get("zoom_link", ""),
                key=f"fellowship_zoom_{source_event_id}",
                help="The link is automatically omitted from offline-event messages.",
            )
            if is_bible_study:
                st.caption("Bible-study details are private planning data joined from the matching Helpers row.")
                bible_passage = st.text_input(
                    "Bible passage", value=source_passage or "待確認",
                    key=f"fellowship_passage_{source_event_id}",
                )
                discussion_leader = st.text_input(
                    "Discussion leader", value=helper_event.get("leader", "") or "待確認",
                    key=f"fellowship_leader_{source_event_id}",
                )
                helper_names = [
                    st.text_input(
                        "Helper 1", value=helper_event.get("helper_one", "") or "待確認",
                        key=f"fellowship_helper_one_{source_event_id}",
                    ),
                    st.text_input(
                        "Helper 2", value=helper_event.get("helper_two", "") or "待確認",
                        key=f"fellowship_helper_two_{source_event_id}",
                    ),
                ]
            else:
                bible_passage, discussion_leader, helper_names = "", "", []
            delivery_time = st.time_input("Wednesday delivery time", value=time(9, 0), key=f"fellowship_delivery_{source_event_id}")
            notes = st.text_area(
                "Special instructions", value=source_event.get("internal_notes", ""),
                key=f"fellowship_notes_{source_event_id}",
            )
            draft_clicked = st.form_submit_button("Create preview", icon=":material/edit_note:", type="primary")
        if draft_clicked:
            st.session_state.ministry_preview = {
                "workflow_type": MinistryWorkflowType.FELLOWSHIP_REMINDER,
                "title": f"Friday fellowship · {event_date.isoformat()}",
                "destination": "Bible fellowship LINE group", "destination_key": "bible",
                "message": build_fellowship_reminder(
                    event_date, topic, location, start.strftime("%-I:%M %p"), notes,
                    meeting_mode=meeting_mode, zoom_link=zoom_link,
                    bible_passage=bible_passage, leader=discussion_leader,
                    helpers=helper_names,
                ),
                "scheduled_for": datetime.combine(event_date - timedelta(days=2), delivery_time),
                "source_type": "26H2-Calendar-Public",
                "source_ref": source_event.get("event_id", "Manual fallback"),
            }
    elif workflow == "Pastor email":
        st.subheader("Pastor email extraction")
        st.caption("HouseholdOS monitors the selected inbox every five minutes while this page is open. Matching mail prefills a reviewable draft; it is never sent automatically.")
        output_kind = st.segmented_control(
            "Create", ["Saturday online prayer", "Sunday message forecast"],
            default="Saturday online prayer",
        )
        gmail_rule = pastor_gmail_rule(output_kind)
        pastor_inbox_monitor(gmail_rule)
        gmail_candidate = st.session_state.get(f"pastor_gmail_candidate_{gmail_rule.key}")
        candidate_id = gmail_candidate.message_id if gmail_candidate else "manual"
        candidate_received = gmail_candidate.received_at.date() if gmail_candidate and gmail_candidate.received_at else today
        default_event_details = (
            "週六線上禱告會（請確認郵件中的日期、時間及 Zoom 連結）"
            if output_kind == "Saturday online prayer"
            else "主日信息預告（請確認郵件中的講題及經文）"
        )
        with st.form("pastor_source_form"):
            uploaded = st.file_uploader("Pastor email", type=["eml", "txt"])
            raw_source = st.text_area(
                "Email or WeChat content",
                value=gmail_candidate.raw_email if gmail_candidate else "",
                height=220,
                key=f"pastor_raw_{gmail_rule.key}_{candidate_id}",
            )
            pastor_name = st.text_input("Pastor attribution", value="Bin Qian")
            event_details = st.text_area(
                "Event details shown above the extracted message",
                value=default_event_details,
                key=f"pastor_details_{gmail_rule.key}_{candidate_id}",
            )
            source_ref = st.text_input(
                "Source reference",
                value=gmail_candidate.subject if gmail_candidate else "Manual email or WeChat capture",
                key=f"pastor_ref_{gmail_rule.key}_{candidate_id}",
            )
            source_time = st.date_input("Source received date", value=candidate_received)
            extract_clicked = st.form_submit_button("Extract and create preview", icon=":material/auto_awesome:", type="primary")
        if extract_clicked:
            uploaded_text = uploaded.getvalue().decode("utf-8", errors="replace") if uploaded else ""
            content = uploaded_text or raw_source
            if not content.strip():
                st.warning("Paste or upload the source first.")
            else:
                extracted = extract_pastor_email(content, pastor_name.strip() or "牧師")
                is_prayer = output_kind == "Saturday online prayer"
                event_day = next_weekday(5 if is_prayer else 6)
                delivery_day = next_weekday(5)
                st.session_state.ministry_source_warnings = extracted.warnings
                st.session_state.ministry_preview = {
                    "workflow_type": MinistryWorkflowType.ONLINE_PRAYER if is_prayer else MinistryWorkflowType.SUNDAY_FORECAST,
                    "title": f"{output_kind} · {event_day.isoformat()}",
                    "destination": "Bible fellowship LINE group", "destination_key": "bible",
                    "message": build_pastor_event_announcement(extracted, "online_prayer" if is_prayer else "sunday_forecast", event_details),
                    "scheduled_for": datetime.combine(delivery_day, time(7, 30)),
                    "source_type": f"Gmail: {gmail_rule.account_email}" if gmail_candidate else "Pastor email or WeChat capture",
                    "source_ref": source_ref or extracted.subject,
                    "source_timestamp": datetime.combine(source_time, time()),
                }
    else:
        st.subheader("Bible cowork preparation reminder")
        st.caption("Select a Helpers calendar event to prefill every field. Review and edit the assignments before creating the message.")
        helpers_sheet = "26H2-Calendar-Helpers"
        helpers_events = st.session_state.get("church_calendar_events", {}).get(helpers_sheet, [])
        if not helpers_events and readiness["google_apps_script.update_and_sync"]:
            with st.spinner("Loading Bible-study assignments from the Helpers calendar…"):
                helper_source_result = list_sheet_events(runtime.settings, helpers_sheet)
            if helper_source_result.success:
                event_cache = st.session_state.setdefault("church_calendar_events", {})
                event_cache[helpers_sheet] = helper_source_result.events
                helpers_events = helper_source_result.events
            else:
                st.warning(f"Helpers calendar could not be loaded: {helper_source_result.detail}")

        upcoming_bible_events = sorted(
            [
                item for item in helpers_events
                if parse_sheet_date(item.get("date", ""))
                and parse_sheet_date(item.get("date", "")) >= today
                and "查經" in f"{item.get('activity_type', '')} {item.get('title', '')}"
                and item.get("status") not in {"已取消", "取消"}
            ],
            key=lambda item: parse_sheet_date(item.get("date", "")),
        )
        cowork_event_labels = {
            f"{item.get('date', '')} · {item.get('title', '')} · {item.get('leader', '')}": item
            for item in upcoming_bible_events
        }
        selected_cowork_label = st.selectbox(
            "Source Bible-study event",
            options=list(cowork_event_labels),
            placeholder="No upcoming Bible-study event found",
        ) if cowork_event_labels else None
        cowork_event = cowork_event_labels.get(selected_cowork_label, {})
        cowork_event_id = cowork_event.get("event_id", "manual")
        default_study_date = (
            parse_sheet_date(cowork_event.get("date", ""))
            or next_weekday(4) + timedelta(days=7)
        )
        default_passage = cowork_event.get("bible_passage", "") or cowork_event.get("title", "") or "待確認"
        default_leader = cowork_event.get("leader", "") or "待確認"
        default_helper_one = cowork_event.get("helper_one", "") or "待確認"
        default_helper_two = cowork_event.get("helper_two", "") or "待確認"
        matching_materials = [
            item for item in runtime.repository.list_bible_materials()
            if item.study_date == default_study_date
        ]
        default_material_url = matching_materials[0].drive_url if matching_materials else "待補"
        default_delivery = datetime.combine(default_study_date, time(9, 0)) - timedelta(days=10, hours=12)

        with st.form(f"cowork_draft_form_{cowork_event_id}"):
            study_date = st.date_input(
                "Bible study date", value=default_study_date,
                key=f"cowork_date_{cowork_event_id}",
            )
            passage = st.text_input(
                "Passage or topic", value=default_passage,
                key=f"cowork_passage_{cowork_event_id}",
            )
            leader = st.text_input(
                "Discussion leader", value=default_leader,
                key=f"cowork_leader_{cowork_event_id}",
            )
            helper_one = st.text_input(
                "Helper 1", value=default_helper_one,
                key=f"cowork_helper_one_{cowork_event_id}",
            )
            helper_two = st.text_input(
                "Helper 2", value=default_helper_two,
                key=f"cowork_helper_two_{cowork_event_id}",
            )
            material_url = st.text_input(
                "Preparation material link", value=default_material_url,
                key=f"cowork_material_{cowork_event_id}",
                help="A material with the same study date is selected from the Bible materials library; otherwise this is marked 待補.",
            )
            reminder_date = st.date_input(
                "Reminder delivery date", value=default_delivery.date(),
                key=f"cowork_reminder_date_{cowork_event_id}",
            )
            reminder_time = st.time_input(
                "Reminder delivery time", value=default_delivery.time(),
                key=f"cowork_reminder_time_{cowork_event_id}",
            )
            cowork_clicked = st.form_submit_button("Create preview", icon=":material/edit_note:", type="primary")
        if cowork_clicked:
            scheduled_for = datetime.combine(reminder_date, reminder_time)
            st.session_state.ministry_preview = {
                "workflow_type": MinistryWorkflowType.BIBLE_COWORK_PREP,
                "title": f"Bible cowork preparation · {study_date.isoformat()}",
                "destination": "Helpers LINE group", "destination_key": "helpers",
                "message": build_bible_cowork_reminder(study_date, passage, leader, helper_one, helper_two, material_url),
                "scheduled_for": scheduled_for,
                "source_type": "26H2-Calendar-Helpers / administrator input",
                "source_ref": cowork_event.get("event_id", "Manual fallback"),
            }

    preview = st.session_state.get("ministry_preview")
    if preview:
        st.divider()
        st.subheader("Review exact LINE payload")
        for warning in st.session_state.get("ministry_source_warnings", []):
            st.warning(warning, icon=":material/warning:")
        preview_identity = abs(hash((preview["title"], preview.get("source_ref", ""))))
        edited_message = st.text_area(
            "Message", value=preview["message"], height=280,
            key=f"ministry_preview_editor_{preview_identity}",
        )
        st.caption(f"Destination: {preview['destination']} · Proposed time: {preview['scheduled_for'].strftime('%Y-%m-%d %-I:%M %p')}")
        if st.button("Queue this exact message for approval", icon=":material/approval:", type="primary"):
            approval_id = queue_line_draft(**{**preview, "message": edited_message})
            st.session_state.pop("ministry_preview", None)
            st.session_state.pop("ministry_source_warnings", None)
            st.toast(f"Queued as approval #{approval_id}", icon=":material/check_circle:")
            st.rerun()

with materials_tab:
    st.subheader("Bible study preparation library")
    st.caption("Keep files in Drive; HouseholdOS stores searchable metadata and stable links.")
    with st.form("add_bible_material"):
        title = st.text_input("Material title")
        passage = st.text_input("Passage or topic")
        study_date = st.date_input("Study date", value=None)
        drive_url = st.text_input("Google Drive or Google Doc link")
        storage = st.selectbox("Storage location", ["S&L Google Drive", "Personal Google Drive"])
        material_status = st.selectbox("Material status", ["Source", "Draft", "Reviewed", "Final"])
        material_notes = st.text_area("Notes")
        add_material = st.form_submit_button("Add to library", icon=":material/library_add:", type="primary")
    if add_material:
        if not title.strip() or not drive_url.strip():
            st.warning("Title and Drive link are required.")
        else:
            runtime.repository.create_bible_material(NewBibleStudyMaterial(
                title=title, passage=passage, study_date=study_date, drive_url=drive_url,
                storage_location=storage, status=material_status, notes=material_notes,
            ))
            st.toast("Material added", icon=":material/check_circle:")
            st.rerun()
    search = st.text_input("Search materials", placeholder="Title, passage, or notes")
    materials = runtime.repository.list_bible_materials(search)
    if materials:
        st.dataframe([
            {"Title": item.title, "Passage": item.passage, "Study date": item.study_date,
             "Status": item.status, "Location": item.storage_location, "Drive link": item.drive_url}
            for item in materials
        ], hide_index=True, column_config={"Drive link": st.column_config.LinkColumn("Drive link")})
        with st.expander("Bible agent handoff", icon=":material/psychology:"):
            st.write("Use reviewed library sources with this contract:")
            st.code("Create a Bible-study preparation draft grounded only in the supplied Drive materials. Return passage context, observation questions, interpretation questions, application questions, leader notes, and citations to source links. Mark uncertainty. Do not publish; return a draft for human theological review.", language=None)
    else:
        st.info("No matching materials yet.")
    if any(item.storage_location == "Personal Google Drive" for item in materials):
        st.warning("Move shared ministry originals to the S&L-owned Drive folder, then update their links here. Keep personal originals until links and permissions are verified.")

with calendar_tab:
    st.subheader("Church calendar")
    st.caption("Browse, create, change, or cancel events here. The spreadsheet remains the source of truth.")
    sheet_label = st.segmented_control(
        "Calendar source", ["Public", "Helpers"], default="Public",
        key="church_calendar_source",
    )
    sheet = f"26H2-Calendar-{sheet_label}"
    if st.button("Refresh calendar", icon=":material/refresh:"):
        with st.spinner("Loading events from the spreadsheet…"):
            result = list_sheet_events(runtime.settings, sheet)
        if result.success:
            event_cache = st.session_state.setdefault("church_calendar_events", {})
            event_cache[sheet] = result.events
            st.toast(f"Loaded {len(result.events)} events", icon=":material/check_circle:")
        else:
            st.error(result.detail)

    loaded_events = st.session_state.get("church_calendar_events", {}).get(sheet, [])
    event_labels = {
        f"{item['event_id']} · {item.get('date', '')} · {item.get('title', '')} · {item.get('status', '')}": item["event_id"]
        for item in loaded_events
    }

    view_tab, one_pager_tab, create_tab, coordination_tab, manage_tab = st.tabs(
        ["Calendar view", "One-page schedule", "Create event", "Helper coordination", "Change or cancel"]
    )
    with view_tab:
        month_value = st.date_input("Month to display", value=today.replace(day=1), key="church_calendar_month")
        if not loaded_events:
            st.info("Select a source and refresh the calendar to display events.")
        else:
            parsed_events = [
                {**item, "parsed_date": parse_sheet_date(item.get("date", ""))}
                for item in loaded_events
            ]
            parsed_events = [item for item in parsed_events if item["parsed_date"]]
            month_events = [
                item for item in parsed_events
                if item["parsed_date"].year == month_value.year
                and item["parsed_date"].month == month_value.month
            ]
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"### {month_value.strftime('%B %Y')}")
                st.badge(f"{len(month_events)} events", color="blue")
            header_columns = st.columns(7)
            for column, weekday in zip(header_columns, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
                column.caption(weekday, text_alignment="center")
            weeks = month_calendar.Calendar(firstweekday=0).monthdatescalendar(
                month_value.year, month_value.month
            )
            for week in weeks:
                day_columns = st.columns(7, gap="small")
                for column, calendar_day in zip(day_columns, week):
                    day_events = [item for item in month_events if item["parsed_date"] == calendar_day]
                    with column.container(border=True, height=155, gap=None):
                        if calendar_day.month == month_value.month:
                            st.markdown(f"**{calendar_day.day}**")
                            for item in day_events[:3]:
                                start_text = item.get("start_time") or "All day"
                                status_icon = "✓" if item.get("status") != "已取消" else "×"
                                st.caption(f"{status_icon} {start_text}")
                                st.markdown(item.get("title") or "Untitled")
                            if len(day_events) > 3:
                                st.caption(f"+{len(day_events) - 3} more")
                        else:
                            st.caption(str(calendar_day.day))
            if month_events:
                st.subheader("Event details")
                for item in sorted(month_events, key=lambda value: (value["parsed_date"], value.get("start_time", ""))):
                    with st.container(border=True):
                        with st.container(horizontal=True, vertical_alignment="center"):
                            st.markdown(f"**{item['parsed_date'].strftime('%a, %b %-d')} · {item.get('title', '')}**")
                            st.badge(item.get("status") or "No status")
                        st.caption(
                            f"{item.get('start_time') or 'All day'}–{item.get('end_time') or ''} · "
                            f"{item.get('location') or 'Location pending'} · {item['event_id']}"
                        )

    with one_pager_tab:
        st.caption("View the complete 26H2 schedule without returning to the spreadsheet. Public mode excludes private helper planning fields.")
        one_pager_mode = st.segmented_control(
            "One-pager content", ["Public schedule", "Admin helper plan"],
            default="Public schedule", key="church_one_pager_mode",
        )
        include_cancelled = st.checkbox(
            "Include cancelled events", value=False, key="church_one_pager_cancelled"
        )
        if st.button("Load all church events", icon=":material/refresh:"):
            event_cache = st.session_state.setdefault("church_calendar_events", {})
            load_errors = []
            with st.spinner("Loading Public and Helpers schedules…"):
                for source_sheet in ("26H2-Calendar-Public", "26H2-Calendar-Helpers"):
                    source_result = list_sheet_events(runtime.settings, source_sheet)
                    if source_result.success:
                        event_cache[source_sheet] = source_result.events
                    else:
                        load_errors.append(source_result.detail)
            if load_errors:
                st.error(" · ".join(load_errors))
            else:
                st.toast("Loaded the complete church schedule", icon=":material/check_circle:")

        one_pager_cache = st.session_state.get("church_calendar_events", {})
        public_schedule = one_pager_cache.get("26H2-Calendar-Public", [])
        helper_schedule = one_pager_cache.get("26H2-Calendar-Helpers", [])
        required_loaded = bool(public_schedule) and (
            one_pager_mode == "Public schedule" or bool(helper_schedule)
        )
        if not required_loaded:
            st.info("Select Load all church events to build the one-page schedule.")
        else:
            one_pager_rows, one_pager_markdown = build_church_one_pager(
                public_schedule,
                helper_schedule,
                include_private=one_pager_mode == "Admin helper plan",
                include_cancelled=include_cancelled,
            )
            with st.container(horizontal=True):
                st.metric("Events", len(one_pager_rows), border=True)
                st.metric(
                    "Bible studies",
                    sum("查經" in f"{row.get('Type', '')} {row.get('Event', '')}" for row in one_pager_rows),
                    border=True,
                )
                st.download_button(
                    "Download Markdown",
                    data=one_pager_markdown,
                    file_name=(
                        "SL-26H2-admin-helper-plan.md"
                        if one_pager_mode == "Admin helper plan"
                        else "SL-26H2-public-schedule.md"
                    ),
                    mime="text/markdown",
                    icon=":material/download:",
                )
            st.dataframe(
                one_pager_rows,
                hide_index=True,
                height=620,
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="MMM D, YYYY"),
                    "Event": st.column_config.TextColumn("Event", pinned=True),
                },
            )

    with create_tab:
        st.caption("Every new church event creates matched Public and Helpers rows with one stable Event ID. Planning details stay in Helpers.")
        with st.form("create_church_event"):
            with st.container(horizontal=True):
                st.badge("Public calendar", color="blue", icon=":material/groups:")
                st.badge("Helpers calendar", color="violet", icon=":material/group_work:")
            title = st.text_input("Event title")
            event_date = st.date_input("Event date", value=next_weekday(4))
            start_time = st.time_input("Start time", value=time(19, 30))
            end_time = st.time_input("End time", value=time(21, 0))
            location = st.text_input("Location", value="詩班房")
            zoom_link = st.text_input("Zoom link")
            activity_type = st.selectbox("Activity type", ["查經", "團契活動", "禱告會", "聚餐", "其他"])
            event_status = st.selectbox("Initial status", ["草稿", "已確認"])
            st.caption("Helpers details apply only to the Helpers tab.")
            leader = st.text_input("Discussion leader")
            helper_one = st.text_input("Helper 1")
            helper_two = st.text_input("Helper 2")
            create_reason = st.text_area("Reason or planning note")
            queue_create = st.form_submit_button("Queue new event for approval", icon=":material/add_circle:", type="primary")
        if queue_create:
            if not title.strip():
                st.warning("Enter an event title.")
            elif end_time <= start_time:
                st.warning("End time must be after start time.")
            else:
                event_id = f"CH-{event_date.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
                target_sheets = ["26H2-Calendar-Public", "26H2-Calendar-Helpers"]
                common_changes = {
                    "日期": event_date.strftime("%-m/%-d/%Y"),
                    "小組安排": title.strip(),
                    "教會查經安排": title.strip(),
                    "開始時間": start_time.strftime("%-I:%M %p"),
                    "結束時間": end_time.strftime("%-I:%M %p"),
                    "地點": location.strip(),
                    "Zoom連結": zoom_link.strip(),
                    "活動狀態": event_status,
                    "建議抵達時間": (datetime.combine(event_date, start_time) - timedelta(minutes=15)).strftime("%-I:%M %p"),
                }
                request_id = runtime.repository.propose_external_action(
                    tool_name="google_apps_script.create_and_sync",
                    action="Create church event and synchronize calendars",
                    target=" + ".join(target_sheets),
                    payload={
                        "bridge_action": "create_event_and_sync",
                        "sheets": target_sheets, "event_id": event_id,
                        "changes": common_changes,
                        "sheet_changes": {
                            "26H2-Calendar-Helpers": {
                                "活動類型": activity_type, "查經帶領": leader.strip(),
                                "協助1": helper_one.strip(), "協助2": helper_two.strip(),
                                "同工": "、".join(
                                    name for name in [leader.strip(), helper_one.strip(), helper_two.strip()]
                                    if name
                                ),
                                "預備提醒時間（提前1.5週）": "提前1.5週",
                            }
                        },
                        "reason": create_reason,
                    },
                )
                st.success(f"New event {event_id} is waiting in approval #{request_id}.")

    with coordination_tab:
        st.caption("Update the complete event-specific Bible team in one approval. Select Helpers above and refresh first.")
        if sheet != "26H2-Calendar-Helpers":
            st.info("Change Calendar source to Helpers, then select Refresh calendar.")
        else:
            selected_helper_event = st.selectbox(
                "Bible study event", options=list(event_labels), accept_new_options=True,
                placeholder="Refresh events or type a stable Event ID",
                key="helper_coordination_event",
            )
            helper_event_id = event_labels.get(selected_helper_event, selected_helper_event or "")
            current_event = next(
                (item for item in loaded_events if item.get("event_id") == helper_event_id), {}
            )
            event_widget_key = helper_event_id or "unselected"

            def confirmation_options(current_value):
                options = ["未確認", "已確認"]
                if current_value and current_value not in options:
                    options.insert(0, current_value)
                return options

            with st.form(f"helper_coordination_form_{event_widget_key}"):
                leader = st.text_input("Discussion leader", value=current_event.get("leader", ""), key=f"coord_leader_{event_widget_key}")
                leader_email = st.text_input("Leader email", value=current_event.get("leader_email", ""), key=f"coord_leader_email_{event_widget_key}")
                leader_confirmation = st.selectbox(
                    "Leader confirmation",
                    confirmation_options(current_event.get("leader_confirmation", "")),
                    key=f"coord_leader_confirmation_{event_widget_key}",
                )
                helper_one = st.text_input("Helper 1", value=current_event.get("helper_one", ""), key=f"coord_helper_one_{event_widget_key}")
                helper_one_email = st.text_input("Helper 1 email", value=current_event.get("helper_one_email", ""), key=f"coord_helper_one_email_{event_widget_key}")
                helper_one_confirmation = st.selectbox(
                    "Helper 1 confirmation",
                    confirmation_options(current_event.get("helper_one_confirmation", "")),
                    key=f"coord_helper_one_confirmation_{event_widget_key}",
                )
                helper_two = st.text_input("Helper 2", value=current_event.get("helper_two", ""), key=f"coord_helper_two_{event_widget_key}")
                helper_two_email = st.text_input("Helper 2 email", value=current_event.get("helper_two_email", ""), key=f"coord_helper_two_email_{event_widget_key}")
                helper_two_confirmation = st.selectbox(
                    "Helper 2 confirmation",
                    confirmation_options(current_event.get("helper_two_confirmation", "")),
                    key=f"coord_helper_two_confirmation_{event_widget_key}",
                )
                preparation_reminder = st.text_input(
                    "Preparation reminder", value=current_event.get("preparation_reminder", "") or "提前1.5週",
                    key=f"coord_preparation_reminder_{event_widget_key}",
                )
                internal_notes = st.text_area("Coordination notes", value=current_event.get("internal_notes", ""), key=f"coord_notes_{event_widget_key}")
                send_invitations = st.checkbox(
                    "After updating, send Google Calendar invitations to the assigned leader and helpers",
                    key=f"coord_send_invitations_{event_widget_key}",
                )
                coordination_reason = st.text_area("Reason for assignment change", key=f"coord_reason_{event_widget_key}")
                queue_coordination = st.form_submit_button(
                    "Queue team update for approval", icon=":material/groups:", type="primary"
                )
            if queue_coordination:
                emails = [leader_email.strip(), helper_one_email.strip(), helper_two_email.strip()]
                if not helper_event_id.strip():
                    st.warning("Select or enter an Event ID.")
                elif send_invitations and (not all(emails) or not all("@" in email for email in emails)):
                    st.warning("All three valid-looking email addresses are required before invitations can be sent.")
                else:
                    changes = {
                        "查經帶領": leader.strip(), "帶領者 Email": leader_email.strip(),
                        "帶領確認": leader_confirmation,
                        "協助1": helper_one.strip(), "協助1 Email": helper_one_email.strip(),
                        "協助1確認": helper_one_confirmation,
                        "協助2": helper_two.strip(), "協助2 Email": helper_two_email.strip(),
                        "協助2確認": helper_two_confirmation,
                        "同工": "、".join(
                            name for name in [leader.strip(), helper_one.strip(), helper_two.strip()]
                            if name
                        ),
                        "預備提醒時間（提前1.5週）": preparation_reminder.strip(),
                        "內部備註": internal_notes.strip(),
                        "來賓邀請狀態": "未邀請",
                    }
                    request_id = runtime.repository.propose_external_action(
                        tool_name="google_apps_script.coordinate_helpers",
                        action="Update Bible study team, sync calendar, and optionally invite helpers",
                        target=f"26H2-Calendar-Helpers · {helper_event_id}",
                        payload={
                            "bridge_action": "coordinate_helpers_and_sync",
                            "sheet": "26H2-Calendar-Helpers", "event_id": helper_event_id,
                            "changes": changes, "send_invitations": send_invitations,
                            "reason": coordination_reason.strip(),
                        },
                    )
                    st.success(f"Complete helper-team update is waiting in approval #{request_id}.")
                    if send_invitations:
                        st.warning("Newly assigned helpers will be added as guests. Former guests are not removed automatically, because removal can send cancellation notices.")

    with manage_tab:
        management_action = st.segmented_control(
            "Action", ["Change a field", "Cancel event"], default="Change a field"
        )
        if management_action == "Change a field":
            with st.form("calendar_change_form"):
                selected_event = st.selectbox(
                    "Event ID", options=list(event_labels), accept_new_options=True,
                    placeholder="Refresh events or type a stable Event ID",
                )
                field = st.selectbox("Field to change", ["日期", "小組安排", "教會查經安排", "開始時間", "結束時間", "地點", "Zoom連結", "活動狀態", "建議抵達時間", "查經帶領", "協助1", "協助2", "內部備註"])
                new_value = st.text_input("New value")
                reason = st.text_area("Reason for change")
                queue_change = st.form_submit_button("Queue change for approval", icon=":material/approval:", type="primary")
            if queue_change:
                event_id = event_labels.get(selected_event, selected_event or "")
                if not event_id.strip():
                    st.warning("Event ID is required so the correct row can be updated safely.")
                else:
                    request_id = runtime.repository.propose_external_action(
                        tool_name="google_apps_script.update_and_sync",
                        action=f"Update {field} and synchronize church calendars",
                        target=f"{sheet} · {event_id}",
                        payload={"sheet": sheet, "event_id": event_id.strip(), "changes": {field: new_value}, "reason": reason},
                    )
                    st.success(f"Approval #{request_id} contains the exact row, field, and new value.")
                    st.caption("The reason is stored in the approval's SQLite audit payload, not the spreadsheet or calendar.")
        else:
            st.warning("Cancellation keeps the spreadsheet rows and marks matching calendar events as cancelled. It does not permanently delete history.")
            with st.form("calendar_cancel_form"):
                selected_event = st.selectbox(
                    "Event ID to cancel", options=list(event_labels), accept_new_options=True,
                    placeholder="Refresh events or type a stable Event ID",
                )
                cancel_reason = st.text_area("Cancellation reason")
                acknowledge = st.checkbox("I reviewed the Event ID and want to cancel it in every matching church tab.")
                queue_cancel = st.form_submit_button("Queue cancellation for approval", icon=":material/event_busy:", type="primary")
            if queue_cancel:
                event_id = event_labels.get(selected_event, selected_event or "")
                if not event_id.strip() or not cancel_reason.strip() or not acknowledge:
                    st.warning("Event ID, cancellation reason, and confirmation are required.")
                else:
                    request_id = runtime.repository.propose_external_action(
                        tool_name="google_apps_script.update_and_sync",
                        action="Cancel church event and synchronize calendars",
                        target=f"All matching church tabs · {event_id}",
                        payload={
                            "bridge_action": "cancel_event_and_sync",
                            "sheets": ["26H2-Calendar-Public", "26H2-Calendar-Helpers"],
                            "event_id": event_id.strip(), "reason": cancel_reason.strip(),
                        },
                    )
                    st.success(f"Cancellation is waiting in approval #{request_id}.")
    if not readiness["google_apps_script.update_and_sync"]:
        st.info("Setup needed: deploy Code.gs as a web app and configure its URL and shared secret. The edit trigger can still handle changes made directly in Sheets.")

with history_tab:
    st.subheader("Ministry draft history")
    if not drafts:
        st.info("No ministry drafts have been queued yet.")
    for draft in drafts:
        linked = next((item for item in approvals if item.id == draft.approval_request_id), None)
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"**{draft.title}**")
                st.badge((linked.execution_status or linked.status) if linked else draft.status.value)
            st.caption(f"{draft.destination} · Source: {draft.source_type} · Approval #{draft.approval_request_id}")
            with st.expander("Message"):
                st.text(draft.message)
