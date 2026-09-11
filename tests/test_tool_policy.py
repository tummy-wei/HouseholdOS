import unittest

from householdos.safety.tool_policy import (
    Approval,
    ApprovalRequired,
    ExternalTool,
    ExternalToolPolicy,
    ToolAccess,
)


class ExternalToolPolicyTests(unittest.TestCase):
    def test_read_only_tool_does_not_require_approval(self) -> None:
        tool = ExternalTool("calendar.search")
        ExternalToolPolicy.authorize(tool)
        self.assertFalse(ExternalToolPolicy.sdk_needs_approval(tool))

    def test_write_tool_requires_matching_explicit_approval(self) -> None:
        tool = ExternalTool("calendar.create", ToolAccess.WRITE)

        with self.assertRaises(ApprovalRequired):
            ExternalToolPolicy.authorize(tool)
        with self.assertRaises(ApprovalRequired):
            ExternalToolPolicy.authorize(tool, Approval("email.send", True))

        ExternalToolPolicy.authorize(tool, Approval("calendar.create", True))
        self.assertTrue(ExternalToolPolicy.sdk_needs_approval(tool))


if __name__ == "__main__":
    unittest.main()
