import os
import sys
from rich.console import Console, Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from .display import safe_display
from ..context.collector import EnvironmentContext
from ..engine.schema import CommandProposal
from ..safety.validator import SafetyAssessment

console = Console()


def show_card(query: str, context: EnvironmentContext, proposal: CommandProposal, assessment: SafetyAssessment) -> None:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(overflow="fold")
    table.add_row("Query", Text(safe_display(query)))
    git = (context.git_branch or ("detached HEAD" if context.git_detached else "unknown")) if context.is_git_repo else "not a repository"
    if context.is_git_repo and context.git_dirty_count is not None:
        git += " [clean]" if context.git_dirty_count == 0 else f" [{context.git_dirty_count} changed]"
    table.add_row("Environment", Text(safe_display(f"{context.os} ({context.shell}) | Git: {git}")))
    table.add_row("Command", Syntax(safe_display(proposal.command), "powershell" if "powershell" in context.shell.lower() or "pwsh" in context.shell.lower() else "bash", word_wrap=True))
    table.add_row("Explanation", Text(safe_display(proposal.explanation)))
    colors = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "bold red", "CRITICAL": "bold white on red"}
    table.add_row("Risk", Text(assessment.risk_level, style=colors[assessment.risk_level]))
    if proposal.requires_sudo:
        table.add_row("Privileges", Text("May require elevated privileges", style="yellow"))
    for warning in assessment.warnings:
        table.add_row("Warning", Text(safe_display(warning), style="bold yellow"))
    if assessment.blocked:
        table.add_row("Blocked", Text("Known critical pattern; execution is disabled.", style="bold red"))
    console.print(Panel(Group(table), title="VocalCLI", border_style="cyan"))


def action() -> str:
    if not sys.stdin.isatty():
        return "q"
    console.print("[bold][Enter][/bold] Run  •  [bold]e[/bold] Edit  •  [bold]c[/bold] Copy  •  [bold]Esc/q[/bold] Cancel")
    if os.name == "nt":
        import msvcrt
        key = msvcrt.getwch()
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd, when=termios.TCSANOW)
            key = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if key == "\x03":
        raise KeyboardInterrupt
    return "run" if key in ("\n", "\r") else "q" if key == "\x04" else key.lower()


def edit_command(command: str) -> str:
    try:
        import readline
        readline.set_startup_hook(lambda: readline.insert_text(command))
        try:
            return input("Edit command: ").strip()
        finally:
            readline.set_startup_hook(None)
    except ImportError:
        console.print("Current command:", Text(safe_display(command)))
        return input("Replacement command: ").strip()


def copy_command(command: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(command)
        console.print("Copied to clipboard.")
    except Exception as exc:
        console.print(Text(safe_display(f"Clipboard unavailable: {exc}"), style="red"))
