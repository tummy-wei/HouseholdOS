"""Read-only-by-default policy for current and future external tools."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToolAccess(str, Enum):
    READ_ONLY = "read_only"
    WRITE = "write"


class ApprovalRequired(PermissionError):
    """Raised when a consequential tool action lacks explicit user approval."""


@dataclass(frozen=True)
class ExternalTool:
    name: str
    access: ToolAccess = ToolAccess.READ_ONLY


@dataclass(frozen=True)
class Approval:
    tool_name: str
    approved: bool


class ExternalToolPolicy:
    """Allow reads and gate every external write on a matching approval."""

    @staticmethod
    def authorize(tool: ExternalTool, approval: Approval | None = None) -> None:
        if tool.access is ToolAccess.READ_ONLY:
            return
        if approval is None or not approval.approved or approval.tool_name != tool.name:
            raise ApprovalRequired(
                f"External write tool '{tool.name}' requires explicit user approval"
            )

    @staticmethod
    def sdk_needs_approval(tool: ExternalTool) -> bool:
        """Map policy to the Agents SDK function-tool approval setting."""
        return tool.access is ToolAccess.WRITE
