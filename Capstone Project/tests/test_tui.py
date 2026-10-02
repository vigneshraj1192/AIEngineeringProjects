"""Unit and automated headless interaction tests for Textual TUI."""

import pytest
from codepilot.tui.app import CodePilotApp, GitHubIssuesPanel, ActiveTaskPanel, AgentLogsPanel, HumanApprovalPanel

@pytest.mark.asyncio
async def test_tui_app_mount_and_panels():
    """Verify that the 4-panel TUI layout mounts properly."""
    app = CodePilotApp()
    async with app.run_test() as pilot:
        # Check all 4 panels exist
        assert app.query_one("#panel_issues", GitHubIssuesPanel) is not None
        assert app.query_one("#panel_active", ActiveTaskPanel) is not None
        assert app.query_one("#panel_logs", AgentLogsPanel) is not None
        assert app.query_one("#panel_hitl", HumanApprovalPanel) is not None

        # Verify initial issue listing
        issues_panel = app.query_one("#panel_issues", GitHubIssuesPanel)
        assert issues_panel is not None

        # Test key press 's' (skip) and 'l'
        await pilot.press("s")
        await pilot.press("l")
        await pilot.pause()

        # Stop orchestrator polling
        app.orchestrator.stop_polling()
