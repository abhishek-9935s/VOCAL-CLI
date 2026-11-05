from typer.testing import CliRunner
from vocal.cli import app
from vocal.context.collector import EnvironmentContext
from vocal.engine.schema import CommandProposal
from vocal.terminal.runner import ExecutionResult
import vocal.cli as cli


def proposal(command="git status", risk="LOW"):
    return CommandProposal(command=command, explanation="status", risk_level=risk, target_binary="git", requires_sudo=False, is_destructive=False)


def setup_flow(monkeypatch, commands, actions):
    context = EnvironmentContext(os="Linux", shell="bash", cwd="/tmp")
    monkeypatch.setattr(cli, "get_settings", lambda: {})
    monkeypatch.setattr(cli.ContextCollector, "collect", lambda self: context)
    monkeypatch.setattr(cli, "generate_proposal", lambda *a: next(commands))
    monkeypatch.setattr(cli, "action", lambda: next(actions))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(cli, "show_card", lambda *a: None)


def test_edited_command_is_revalidated(monkeypatch):
    setup_flow(monkeypatch, iter([proposal()]), iter(["e", "run", "q"]))
    monkeypatch.setattr(cli, "edit_command", lambda c: "rm -rf /")
    ran = []
    monkeypatch.setattr(cli, "run_command", lambda c: ran.append(c))
    cli.process_query("test")
    assert ran == []


def test_fix_requires_another_review(monkeypatch):
    setup_flow(monkeypatch, iter([proposal(), proposal("git log")]), iter(["run", "q"]))
    ran = []
    monkeypatch.setattr(cli, "run_command", lambda c: ran.append(c) or ExecutionResult(1, "failed"))
    monkeypatch.setattr(cli.typer, "confirm", lambda *a, **k: True)
    cli.process_query("test")
    assert ran == ["git status"]


def test_cli_missing_key_exits_cleanly(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "get_settings", lambda: {"provider": "openai"})
    result = CliRunner().invoke(app, ["ask", "list files"])
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.output


def test_noninteractive_proposal_never_runs(monkeypatch):
    context = EnvironmentContext(os="Linux", shell="bash", cwd="/tmp")
    monkeypatch.setattr(cli, "get_settings", lambda: {})
    monkeypatch.setattr(cli.ContextCollector, "collect", lambda self: context)
    monkeypatch.setattr(cli, "generate_proposal", lambda *a: proposal())
    monkeypatch.setattr(cli, "show_card", lambda *a: None)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    ran = []
    monkeypatch.setattr(cli, "run_command", lambda c: ran.append(c))
    cli.process_query("test")
    assert ran == []


def test_critical_model_risk_requires_typed_confirmation(monkeypatch):
    setup_flow(monkeypatch, iter([proposal(risk="CRITICAL")]), iter(["run"]))
    monkeypatch.setattr("builtins.input", lambda _: "wrong")
    ran = []
    monkeypatch.setattr(cli, "run_command", lambda c: ran.append(c))
    cli.process_query("test")
    assert ran == []


def test_command_failure_sets_cli_exit_status(monkeypatch):
    setup_flow(monkeypatch, iter([proposal()]), iter(["run"]))
    monkeypatch.setattr(cli, "run_command", lambda c: ExecutionResult(7, "failed"))
    monkeypatch.setattr(cli.typer, "confirm", lambda *a, **k: False)
    assert cli.process_query("test") == 7
    monkeypatch.setattr(cli, "process_query", lambda query: 7)
    result = CliRunner().invoke(app, ["ask", "test"])
    assert result.exit_code == 7


def test_redirected_output_never_runs(monkeypatch):
    setup_flow(monkeypatch, iter([proposal()]), iter(["run"]))
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False)
    ran = []
    monkeypatch.setattr(cli, "run_command", lambda c: ran.append(c))
    assert cli.process_query("test") == 0
    assert ran == []


def test_doctor_does_not_contact_provider_or_expose_keys(monkeypatch):
    monkeypatch.setattr(cli, "get_settings", lambda: {"provider": "openai", "openai_api_key": "secret", "stt_backend": "openai"})
    monkeypatch.setattr(cli.ContextCollector, "collect", lambda self: EnvironmentContext(os="Linux", shell="bash", cwd="/tmp"))
    monkeypatch.setattr(cli, "_microphone_status", lambda: "unavailable")
    monkeypatch.setattr(cli, "generate_proposal", lambda *args: (_ for _ in ()).throw(AssertionError("must not contact provider")))
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "configured" in result.output and "secret" not in result.output
    assert "No API calls or recordings" in result.output


def test_doctor_missing_key_is_actionable(monkeypatch):
    monkeypatch.setattr(cli, "get_settings", lambda: {"provider": "gemini", "stt_backend": "openai"})
    monkeypatch.setattr(cli.ContextCollector, "collect", lambda self: EnvironmentContext(os="Linux", shell="bash", cwd="/tmp"))
    monkeypatch.setattr(cli, "_microphone_status", lambda: "unavailable")
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "GEMINI_API_KEY: missing" in result.output


def test_version_flag():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "VocalCLI" in result.output
