"""Command line interface and runner for CodePilot."""

import sys
import argparse
from codepilot.config import config
from codepilot.tui.app import CodePilotApp
from codepilot.agents.orchestrator import OrchestratorAgent
from codepilot.github.client import github_client
from codepilot.tui.event_bus import event_bus, EventType
from codepilot.guardrails.hitl import hitl
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def run_tui():
    """Launch interactive Textual TUI."""
    app = CodePilotApp()
    app.run()

def run_headless(issue_number: int | None = None, auto_approve: bool = True):
    """Run CodePilot in headless terminal mode with Rich console formatting."""
    console.print(Panel.fit(
        f"[bold cyan]CodePilot[/bold cyan] — Autonomous AI Coding Platform\n"
        f"[yellow]Repository:[/yellow] {config.github_repository} | [yellow]Model:[/yellow] {config.model_name}",
        border_style="cyan"
    ))

    if auto_approve:
        hitl.set_auto_approve(True)
    else:
        # Interactive terminal approval prompt
        def terminal_hitl_handler(req):
            console.print(f"\n[bold red]⚠ APPROVAL REQUIRED:[/bold red] {req.operation}")
            console.print(f"[yellow]Reason:[/yellow] {req.reason}")
            ans = input("Enter decision [approve/reject]: ").strip().lower()
            return "approve" if ans in ("a", "approve", "y", "yes") else "reject"
        hitl.set_approval_handler(terminal_hitl_handler)

    # Attach rich console logger to event bus
    def _on_log(data):
        agent = data.get("agent", "Agent")
        msg = data.get("message", "")
        level = data.get("level", "INFO")
        tool = data.get("tool_call")
        tool_str = f" ({tool})" if tool else ""
        if level == "ERROR":
            console.print(f"[bold red][{agent}]{tool_str} {msg}[/bold red]")
        elif level == "WARNING":
            console.print(f"[bold yellow][{agent}]{tool_str} {msg}[/bold yellow]")
        else:
            console.print(f"[dim][{agent}]{tool_str}[/dim] {msg}")

    event_bus.subscribe(EventType.AGENT_LOG, _on_log)

    orchestrator = OrchestratorAgent()

    if issue_number:
        issue = github_client.get_issue(issue_number)
        if not issue:
            console.print(f"[red]Error: Issue #{issue_number} not found.[/red]")
            sys.exit(1)
        issues = [issue]
    else:
        issues = github_client.list_issues(state="open")

    table = Table(title="Available GitHub Issues")
    table.add_column("Issue #", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Labels", style="magenta")
    table.add_column("Complexity", style="green")

    for iss in issues:
        table.add_row(f"#{iss.number}", iss.title, ", ".join(iss.labels), str(iss.complexity_score or "Auto"))
    console.print(table)

    for iss in issues:
        console.print(f"\n[bold green]>>> Starting autonomous processing for Issue #{iss.number}...[/bold green]")
        status = orchestrator.process_issue(iss)
        console.print(f"[bold]Task finished with status: [cyan]{status.value}[/cyan][/bold]")

    # Save session summary
    summary = orchestrator.stop_polling()

def main():
    parser = argparse.ArgumentParser(description="CodePilot: Autonomous Terminal-based AI Coding Platform")
    parser.add_argument("--mode", choices=["tui", "headless"], default="tui", help="Execution mode (tui or headless)")
    parser.add_argument("--issue", type=int, default=None, help="Specific issue number to solve")
    parser.add_argument("--task", type=str, default=None, help="Execute direct coding task string")
    parser.add_argument("--no-auto-approve", action="store_true", help="Disable auto-approval in headless mode")

    args = parser.parse_args()

    if args.task:
        hitl.set_auto_approve(not args.no_auto_approve)
        orchestrator = OrchestratorAgent()
        orchestrator.execute_manual_task(args.task)
    elif args.mode == "headless":
        run_headless(issue_number=args.issue, auto_approve=not args.no_auto_approve)
    else:
        run_tui()

if __name__ == "__main__":
    main()
