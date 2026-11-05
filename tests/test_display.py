import io
from rich.console import Console
from vocal.context.collector import EnvironmentContext
from vocal.engine.schema import CommandProposal
from vocal.safety.validator import validate_command
from vocal.terminal import ui
from vocal.terminal.display import safe_display


def test_card_escapes_untrusted_terminal_and_bidi_sequences(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(ui, "console", Console(file=stream, force_terminal=False, width=120))
    ctx = EnvironmentContext(os="Linux", shell="bash", cwd="/tmp", is_git_repo=True, git_branch="bad\x1b[2J")
    proposal = CommandProposal(command="echo hi\x1b[2J", explanation="look\u202e", risk_level="LOW", target_binary="echo", requires_sudo=False, is_destructive=False)
    ui.show_card("query\x07", ctx, proposal, validate_command(proposal.command))
    output = stream.getvalue()
    assert "\x1b" not in output and "\x07" not in output and "\u202e" not in output
    assert "\\x1b[2J" in output and "\\x07" in output and "\\u202e" in output
    assert "Blocked" in output


def test_display_allows_newline_and_unicode():
    assert safe_display("नमस्ते\nworld") == "नमस्ते\nworld"


def test_card_does_not_truncate_long_command(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(ui, "console", Console(file=stream, force_terminal=False, width=40))
    command = "echo " + "x" * 120
    proposal = CommandProposal(command=command, explanation="long argument", risk_level="LOW", target_binary="echo", requires_sudo=False, is_destructive=False)
    ctx = EnvironmentContext(os="Linux", shell="bash", cwd="/tmp")
    ui.show_card("test", ctx, proposal, validate_command(command))
    output = stream.getvalue()
    assert output.count("x") >= 120
    assert "…" not in output
