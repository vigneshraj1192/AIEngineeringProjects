"""Textual TUI for CodePilot: 4-panel dashboard with real-time logs and HITL approval."""

from typing import Optional, List, Dict, Any
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Header, Footer, Static, RichLog, Input, Button, Label
from textual.screen import ModalScreen
from textual.binding import Binding

from codepilot.state import TaskStatus, IssueItem
from codepilot.tui.event_bus import event_bus, EventType
from codepilot.guardrails.hitl import hitl
from codepilot.agents.orchestrator import OrchestratorAgent
from codepilot.github.client import github_client
from codepilot.config import config

class NewTaskModal(ModalScreen[str]):
    """Modal input prompt for typing free-form coding tasks ('[i] New task')."""

    DEFAULT_CSS = """
    NewTaskModal {
        align: center middle;
    }
    #dialog {
        padding: 1 2;
        width: 70;
        height: 14;
        border: thick $primary;
        background: $surface;
    }
    #task_input {
        margin: 1 0;
    }
    #button_row {
        align: right middle;
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("📝 Enter Direct Coding Task for CodePilot:")
            yield Input(placeholder="e.g. Fix null pointer in auth handler or add CSV export", id="task_input")
            with Horizontal(id="button_row"):
                yield Button("Cancel", variant="default", id="cancel_btn")
                yield Button("Submit Task", variant="primary", id="submit_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit_btn":
            inp = self.query_one("#task_input", Input)
            if inp.value.strip():
                self.dismiss(inp.value.strip())
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

class InspectModal(ModalScreen[None]):
    """Modal displaying inspection details (diff preview, proposed files)."""

    DEFAULT_CSS = """
    InspectModal {
        align: center middle;
    }
    #inspect_dialog {
        padding: 1 2;
        width: 80;
        height: 24;
        border: thick $warning;
        background: $surface;
    }
    #inspect_content {
        height: 16;
        overflow-y: scroll;
        border: solid $accent;
        padding: 1;
    }
    """

    def __init__(self, details_text: str):
        super().__init__()
        self.details_text = details_text

    def compose(self) -> ComposeResult:
        with Vertical(id="inspect_dialog"):
            yield Label("🔍 Operation Inspection & Diff Preview:")
            yield Static(self.details_text, id="inspect_content")
            yield Button("Close Inspection", variant="default", id="close_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

class GitHubIssuesPanel(Static):
    """Top-Left Panel: Displays real-time GitHub issues feed with status icons."""

    def compose(self) -> ComposeResult:
        yield Label("🐙 GitHub Issues Feed", classes="panel-title")
        yield Static(id="issues_list")

    def update_issues(self, issues: list) -> None:
        lines = []
        for i in issues:
            state = i.get("state", "open")
            num = i.get("number")
            title = i.get("title", "")[:35]
            if state == "open":
                icon = "[green]●[/green]"
            elif state == "in-progress":
                icon = "[yellow]◐[/yellow]"
            else:
                icon = "[cyan]✓[/cyan]"
            lines.append(f"#{num} {title} {icon}")
        content = "\n".join(lines) if lines else "No open issues found."
        self.query_one("#issues_list", Static).update(content)

class ActiveTaskPanel(Static):
    """Top-Right Panel: Displays current task status, agent, skill, and checklist."""

    def compose(self) -> ComposeResult:
        yield Label("⚡ Active Task Details", classes="panel-title")
        yield Static(id="task_info")
        yield Label("📋 Implementation Checklist (write_todos):", classes="sub-title")
        yield Static(id="todo_checklist")

    def update_task(self, task_data: dict) -> None:
        issue = task_data.get("issue", {})
        num = issue.get("number", "-")
        title = issue.get("title", "Idle")
        status = task_data.get("status", "IDLE")
        agent = task_data.get("active_agent", "Orchestrator")
        skill = task_data.get("skill_name", "None")
        retries = task_data.get("retry_count", 0)

        info_text = (
            f"[bold]Issue #{num}:[/bold] {title}\n"
            f"[bold]Status:[/bold] [cyan]{status}[/cyan] | [bold]Agent:[/bold] [yellow]{agent}[/yellow] (retry {retries}/3)\n"
            f"[bold]Skill:[/bold] [magenta]{skill}[/magenta]"
        )
        self.query_one("#task_info", Static).update(info_text)

        todos = task_data.get("todos", [])
        todo_lines = []
        for t in todos:
            desc = t.get("description", "")
            completed = t.get("completed", False)
            mark = "[green][✓][/green]" if completed else "[dim][ ][/dim]"
            todo_lines.append(f"  {mark} {desc}")

        todo_content = "\n".join(todo_lines) if todo_lines else "  [dim]No active todos formulated yet[/dim]"
        self.query_one("#todo_checklist", Static).update(todo_content)

class AgentLogsPanel(Static):
    """Bottom-Left Panel: Streams agent thoughts, tool calls, and execution steps."""

    def compose(self) -> ComposeResult:
        yield Label("📜 Agent Activity & Tool Calls Stream", classes="panel-title")
        yield RichLog(id="log_stream", highlight=True, markup=True, max_lines=500)

    def write_log(self, agent: str, message: str, level: str = "INFO", tool_call: str | None = None) -> None:
        log_box = self.query_one("#log_stream", RichLog)
        badge = f"[bold yellow][{agent}][/bold yellow]"
        if tool_call:
            badge += f" [cyan]({tool_call})[/cyan]"
        
        if level == "ERROR":
            msg = f"[red]{message}[/red]"
        elif level == "WARNING":
            msg = f"[bold orange3]{message}[/bold orange3]"
        else:
            msg = message

        log_box.write(f"{badge} {msg}")

class HumanApprovalPanel(Static):
    """Bottom-Right Panel: Surfaces HITL interrupts and gathers approval."""

    def compose(self) -> ComposeResult:
        yield Label("🛡️ Human-In-The-Loop Approval Gate", classes="panel-title")
        yield Static("[dim]No pending approval requests. Operations running safely.[/dim]", id="hitl_content")
        with Horizontal(id="approval_actions"):
            yield Button("Approve (a)", variant="success", id="btn_approve", disabled=True)
            yield Button("Reject (r)", variant="error", id="btn_reject", disabled=True)
            yield Button("Inspect", variant="default", id="btn_inspect", disabled=True)

    def show_request(self, req: dict) -> None:
        op = req.get("operation", "")
        reason = req.get("reason", "")
        text = (
            f"[bold red]⚠ APPROVAL REQUIRED:[/bold red]\n"
            f"[bold]{op}[/bold]\n"
            f"[yellow]Reason:[/yellow] {reason}\n"
            f"[dim]> Press 'a' to Approve, 'r' to Reject, or Inspect[/dim]"
        )
        self.query_one("#hitl_content", Static).update(text)
        self.query_one("#btn_approve", Button).disabled = False
        self.query_one("#btn_reject", Button).disabled = False
        self.query_one("#btn_inspect", Button).disabled = False

    def clear_request(self, status: str = "approved") -> None:
        text = f"[green]✓ Operation was {status}. Execution resumed.[/green]" if status == "approved" else f"[red]✗ Operation was rejected.[/red]"
        self.query_one("#hitl_content", Static).update(text)
        self.query_one("#btn_approve", Button).disabled = True
        self.query_one("#btn_reject", Button).disabled = True
        self.query_one("#btn_inspect", Button).disabled = True

class CodePilotApp(App):
    """Main Textual Application for CodePilot."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 1.5fr;
        grid-rows: 1fr 1fr;
        background: #0f141c;
        color: #e6edf3;
    }
    Static {
        border: solid #30363d;
        padding: 0 1;
        background: #161b22;
    }
    .panel-title {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
        padding: 0 1;
        width: 100%;
        margin-bottom: 1;
    }
    .sub-title {
        color: #8b949e;
        margin-top: 1;
    }
    #approval_actions {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("i", "new_task", "New task"),
        Binding("s", "skip_issue", "Skip issue"),
        Binding("q", "quit", "Quit"),
        Binding("l", "toggle_logs", "Logs"),
        Binding("a", "approve", "Approve"),
        Binding("r", "reject", "Reject"),
    ]

    def __init__(self, orchestrator: Optional[OrchestratorAgent] = None):
        super().__init__()
        self.orchestrator = orchestrator or OrchestratorAgent()
        self.current_hitl_req: Optional[dict] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield GitHubIssuesPanel(id="panel_issues")
        yield ActiveTaskPanel(id="panel_active")
        yield AgentLogsPanel(id="panel_logs")
        yield HumanApprovalPanel(id="panel_hitl")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "CodePilot — Autonomous AI Coding Platform"
        self.sub_title = f"Repo: {config.github_repository} | Model: {config.model_name}"

        # Subscribe to Event Bus events
        event_bus.subscribe(EventType.ISSUE_LIST_UPDATED, self._on_issues_updated)
        event_bus.subscribe(EventType.TASK_STATE_CHANGED, self._on_task_state_changed)
        event_bus.subscribe(EventType.AGENT_LOG, self._on_agent_log)
        event_bus.subscribe(EventType.HITL_PROMPT, self._on_hitl_prompt)
        event_bus.subscribe(EventType.HITL_RESOLVED, self._on_hitl_resolved)

        # Initial issues load
        issues = [i.model_dump() for i in github_client.list_issues(state="open")]
        self.query_one("#panel_issues", GitHubIssuesPanel).update_issues(issues)

        # Start orchestrator polling
        self.orchestrator.start_polling(interval_seconds=config.poll_interval_seconds)

    def _on_issues_updated(self, data: dict) -> None:
        self.call_from_thread(self.query_one("#panel_issues", GitHubIssuesPanel).update_issues, data.get("issues", []))

    def _on_task_state_changed(self, data: dict) -> None:
        self.call_from_thread(self.query_one("#panel_active", ActiveTaskPanel).update_task, data)

    def _on_agent_log(self, data: dict) -> None:
        self.call_from_thread(
            self.query_one("#panel_logs", AgentLogsPanel).write_log,
            data.get("agent", "Agent"),
            data.get("message", ""),
            data.get("level", "INFO"),
            data.get("tool_call")
        )

    def _on_hitl_prompt(self, data: dict) -> None:
        self.current_hitl_req = data
        self.call_from_thread(self.query_one("#panel_hitl", HumanApprovalPanel).show_request, data)

    def _on_hitl_resolved(self, data: dict) -> None:
        self.current_hitl_req = None
        self.call_from_thread(self.query_one("#panel_hitl", HumanApprovalPanel).clear_request, data.get("status", "resolved"))

    def action_new_task(self) -> None:
        """Handler for '[i] New task' shortcut."""
        def _handle_submitted(task_prompt: Optional[str]):
            if task_prompt:
                event_bus.log("User", f"Dispatched direct task: '{task_prompt}'", level="INFO")
                # Run manual task in worker thread
                self.run_worker(lambda: self.orchestrator.execute_manual_task(task_prompt), thread=True)

        self.push_screen(NewTaskModal(), _handle_submitted)

    def action_skip_issue(self) -> None:
        """Handler for '[s] Skip issue' shortcut."""
        event_bus.log("User", "Skipped currently active issue.", level="WARNING")

    def action_approve(self) -> None:
        """Handler for approving pending HITL request."""
        if self.current_hitl_req:
            req_id = self.current_hitl_req.get("id")
            hitl.resolve(req_id, "approve")

    def action_reject(self) -> None:
        """Handler for rejecting pending HITL request."""
        if self.current_hitl_req:
            req_id = self.current_hitl_req.get("id")
            hitl.resolve(req_id, "reject")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_approve":
            self.action_approve()
        elif event.button.id == "btn_reject":
            self.action_reject()
        elif event.button.id == "btn_inspect":
            details = str(self.current_hitl_req.get("details", "No extra details")) if self.current_hitl_req else "No pending operation."
            self.push_screen(InspectModal(details))
