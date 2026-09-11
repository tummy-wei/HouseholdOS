"""Approval-gated adapters for consequential ministry actions."""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from householdos.config import Settings
from householdos.domain.models import ApprovalRequestRecord
from householdos.safety.tool_policy import Approval, ExternalTool, ExternalToolPolicy, ToolAccess


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    detail: str


@dataclass(frozen=True)
class EventListResult:
    success: bool
    events: list[dict[str, str]]
    detail: str


def _verified_ssl_context() -> ssl.SSLContext:
    """Use the maintained CA bundle because macOS framework Python may lack one."""
    return ssl.create_default_context(cafile=certifi.where())


def adapter_readiness(settings: Settings) -> dict[str, bool]:
    if settings.demo_mode:
        return {
            "line.send": False,
            "line.send.bible": False,
            "line.send.helpers": False,
            "google_apps_script.update_and_sync": False,
            "google_apps_script.create_and_sync": False,
            "google_apps_script.coordinate_helpers": False,
        }
    line_token_ready = bool(settings.line_channel_access_token)
    return {
        "line.send": bool(
            line_token_ready
            and (settings.line_bible_group_id or settings.line_helpers_group_id)
        ),
        "line.send.bible": bool(line_token_ready and settings.line_bible_group_id),
        "line.send.helpers": bool(line_token_ready and settings.line_helpers_group_id),
        "google_apps_script.update_and_sync": bool(
            settings.apps_script_web_app_url and settings.apps_script_shared_secret
        ),
        "google_apps_script.create_and_sync": bool(
            settings.apps_script_web_app_url and settings.apps_script_shared_secret
        ),
        "google_apps_script.coordinate_helpers": bool(
            settings.apps_script_web_app_url and settings.apps_script_shared_secret
        ),
    }


def execute_approved_action(
    request: ApprovalRequestRecord, settings: Settings
) -> ExecutionResult:
    if settings.demo_mode:
        return ExecutionResult(False, "External execution is disabled in capstone demo mode")
    if request.status != "Approved":
        raise PermissionError("Only an explicitly approved action can be executed")
    scheduled_for = request.payload.get("scheduled_for")
    if scheduled_for:
        due_at = datetime.fromisoformat(str(scheduled_for))
        if due_at > datetime.now(due_at.tzinfo):
            raise PermissionError(f"Approved action is scheduled for {due_at.isoformat()}")
    ExternalToolPolicy.authorize(
        ExternalTool(request.tool_name, ToolAccess.WRITE),
        Approval(request.tool_name, True),
    )
    if request.tool_name == "line.send":
        return _send_line_message(request.payload, settings)
    if request.tool_name in {
        "google_apps_script.update_and_sync",
        "google_apps_script.create_and_sync",
        "google_apps_script.coordinate_helpers",
    }:
        return _update_sheet_and_sync(request.payload, settings)
    raise ValueError(f"No execution adapter is registered for {request.tool_name}")


def list_sheet_events(settings: Settings, sheet: str) -> EventListResult:
    """Read event choices through the authenticated bridge; this performs no write."""
    if settings.demo_mode:
        return EventListResult(False, [], "Spreadsheet access is disabled in capstone demo mode")
    if not settings.apps_script_web_app_url or not settings.apps_script_shared_secret:
        return EventListResult(False, [], "Apps Script bridge is not configured")
    body = json.dumps({
        "secret": settings.apps_script_shared_secret,
        "action": "list_events",
        "sheet": sheet,
    })
    http_request = Request(
        settings.apps_script_web_app_url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(http_request, timeout=30, context=_verified_ssl_context()) as response:  # noqa: S310
            result = json.loads(response.read().decode("utf-8"))
        events = result.get("events", []) if result.get("ok") else []
        return EventListResult(bool(result.get("ok")), events, str(result.get("message", "")))
    except (HTTPError, URLError, json.JSONDecodeError) as error:
        return EventListResult(False, [], f"Could not load spreadsheet events: {error}")


def _send_line_message(payload: dict[str, object], settings: Settings) -> ExecutionResult:
    token = settings.line_channel_access_token
    target_key = str(payload.get("destination_key") or "bible")
    group_id = (
        settings.line_helpers_group_id
        if target_key == "helpers"
        else settings.line_bible_group_id
    )
    message = str(payload.get("message") or "").strip()
    if not token or not group_id:
        return ExecutionResult(False, "LINE credentials or destination group ID are not configured")
    if not message:
        return ExecutionResult(False, "Approved LINE payload has no message")

    body = json.dumps({"to": group_id, "messages": [{"type": "text", "text": message}]})
    http_request = Request(
        "https://api.line.me/v2/bot/message/push",
        data=body.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(http_request, timeout=20, context=_verified_ssl_context()) as response:  # noqa: S310
            request_id = response.headers.get("x-line-request-id", "not returned")
            return ExecutionResult(True, f"LINE accepted the message; request ID: {request_id}")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        return ExecutionResult(False, f"LINE returned HTTP {error.code}: {detail}")
    except URLError as error:
        return ExecutionResult(False, f"LINE delivery failed: {error.reason}")


def _update_sheet_and_sync(
    payload: dict[str, object], settings: Settings
) -> ExecutionResult:
    if not settings.apps_script_web_app_url or not settings.apps_script_shared_secret:
        return ExecutionResult(False, "Apps Script web app URL or shared secret is not configured")
    body = json.dumps(
        {
            "secret": settings.apps_script_shared_secret,
            "action": payload.get("bridge_action", "update_event_and_sync"),
            "sheet": payload.get("sheet"),
            "sheets": payload.get("sheets"),
            "event_id": payload.get("event_id"),
            "changes": payload.get("changes"),
            "sheet_changes": payload.get("sheet_changes"),
            "send_invitations": payload.get("send_invitations", False),
        }
    )
    http_request = Request(
        settings.apps_script_web_app_url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(http_request, timeout=30, context=_verified_ssl_context()) as response:  # noqa: S310
            result = json.loads(response.read().decode("utf-8"))
        return ExecutionResult(bool(result.get("ok")), str(result.get("message", result)))
    except (HTTPError, URLError, json.JSONDecodeError) as error:
        return ExecutionResult(False, f"Calendar sync request failed: {error}")
