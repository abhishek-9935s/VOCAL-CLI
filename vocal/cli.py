"""VocalCLI's interactive entry point."""
import sys
import importlib.util
from importlib.metadata import PackageNotFoundError, version
from typing import Optional
import typer
from rich.text import Text
from .audio.capture import AudioUnavailable, record_audio
from .audio.transcriber import TranscriptionError, transcribe
from .config import get_settings
from .context.collector import ContextCollector
from .engine.client import LLMError, generate_proposal
from .safety.validator import validate_command
from .terminal.display import safe_display
from .terminal.runner import run_command
from .terminal.ui import action, console, copy_command, edit_command, show_card

app = typer.Typer(no_args_is_help=False, help="Turn developer requests into reviewed shell commands.")


def process_query(query: str) -> int:
    if not query.strip():
        raise ValueError("Please provide a non-empty query.")
    settings = get_settings()
    failure = None
    while True:
        context = ContextCollector().collect()
        proposal = generate_proposal(query, context, settings, failure)
        while True:
            assessment = validate_command(proposal.command, proposal.risk_level, proposal.is_destructive)
            show_card(query, context, proposal, assessment)
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                console.print("Interactive input and output terminals are required; command will not be executed.")
                return 0
            choice = action()
            if choice in ("q", "\x1b"):
                console.print("Cancelled.")
                return 0
            if choice == "c":
                copy_command(proposal.command)
                return 0
            if choice == "e":
                command = edit_command(proposal.command)
                if command:
                    # A model's explanation no longer necessarily applies after editing.
                    proposal = proposal.model_copy(update={
                        "command": command,
                        "explanation": "Edited by user; original explanation may no longer apply. Review the entire command.",
                        # Do not imply an edited command is known to be safe.
                        "risk_level": "MEDIUM" if proposal.risk_level == "LOW" else proposal.risk_level,
                    })
                continue
            if choice != "run":
                continue
            if assessment.blocked:
                console.print("[bold red]Execution blocked by the safety gate. Edit or cancel.[/bold red]")
                continue
            if assessment.risk_level == "CRITICAL":
                if input("DANGEROUS ACTION: Type CONFIRM to run this command: ") != "CONFIRM":
                    console.print("Cancelled.")
                    return 0
            result = run_command(proposal.command)
            if result.exit_code == 0:
                return 0
            console.print(f"Command exited with status {result.exit_code}.")
            if not typer.confirm("Analyze the failure and propose a fix?", default=False):
                return min(255, result.exit_code if result.exit_code > 0 else 128 - result.exit_code)
            failure = {"command": proposal.command, "exit_code": result.exit_code, "output_tail": result.output_tail}
            break


def _handle_query(query: str) -> None:
    try:
        exit_code = process_query(query)
        if exit_code:
            raise typer.Exit(exit_code)
    except (LLMError, ValueError, OSError) as exc:
        console.print(Text(safe_display(f"Error: {exc}"), style="red"))
        raise typer.Exit(1)
    except (KeyboardInterrupt, EOFError):
        console.print("\nCancelled.")
        raise typer.Exit(130)


@app.command()
def ask(query: Optional[str] = typer.Argument(None, help="Natural-language request; omit to be prompted.")) -> None:
    """Translate a typed request and review the proposed command."""
    try:
        if query is None:
            query = input("Your request: ")
        _handle_query(query)
    except (KeyboardInterrupt, EOFError):
        console.print("\nCancelled.")
        raise typer.Exit(130)


@app.command()
def voice() -> None:
    """Record a voice request, or fall back to typing if audio is unavailable."""
    try:
        settings = get_settings()
        input("Press Enter to start recording; stop speaking to finish: ")
        console.print("Listening (up to 30 seconds)…")
        try:
            audio = record_audio()
            query = transcribe(audio, settings)
            console.print("Transcription:", Text(safe_display(query)))
        except (AudioUnavailable, TranscriptionError) as exc:
            console.print(Text(safe_display(str(exc)), style="yellow"))
            query = input("No audio transcription available. Type your query: ")
        _handle_query(query)
    except (KeyboardInterrupt, EOFError):
        console.print("\nCancelled.")
        raise typer.Exit(130)
    except (ValueError, OSError) as exc:
        console.print(Text(safe_display(f"Error: {exc}"), style="red"))
        raise typer.Exit(1)


@app.command("config")
def config_command() -> None:
    """Show effective settings without exposing API keys."""
    try:
        settings = get_settings()
    except ValueError as exc:
        console.print(Text(safe_display(f"Error: {exc}"), style="red"))
        raise typer.Exit(1)
    # Only print known non-secret settings; arbitrary config fields may contain secrets.
    for key in ("provider", "model", "stt_backend", "whisper_model"):
        if key in settings:
            console.print(Text(safe_display(f"{key}: {settings[key]}")))
    for key in ("openai_api_key", "gemini_api_key"):
        if settings.get(key):
            console.print(Text(f"{key}: [configured]"))


def _microphone_status() -> str:
    try:
        import sounddevice as sd
        device = sd.query_devices(kind="input")
        return "available: " + str(device.get("name", "input device"))
    except (ImportError, OSError):
        return "audio dependencies or PortAudio unavailable; install the audio extra"
    except Exception as exc:
        return f"unavailable: {exc}"


@app.command()
def doctor() -> None:
    """Check local setup without calling a model or recording audio."""
    try:
        settings = get_settings()
        provider = settings["provider"].lower()
        if provider not in {"openai", "gemini"}:
            raise ValueError(f"Unsupported provider: {provider}. Choose openai or gemini.")
        context = ContextCollector().collect()
        key_name = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
        key_present = bool(settings.get(f"{provider}_api_key"))
        model = settings.get("model") or ("gpt-4o-mini" if provider == "openai" else "gemini-2.5-flash")
        backend = settings["stt_backend"].lower()
        if backend not in {"openai", "local"}:
            raise ValueError(f"Unsupported transcription backend: {backend}. Choose openai or local.")
        console.print(Text(safe_display(f"Provider: {provider} | model: {model}")))
        console.print(Text(f"{key_name}: {'configured' if key_present else 'missing'}"))
        console.print(Text(safe_display(f"Environment: {context.os} | shell: {context.shell} | cwd: {context.cwd}")))
        console.print(Text(f"Git: {'repository detected' if context.is_git_repo else 'not a repository or unavailable'}"))
        console.print(Text(safe_display(f"Microphone: {_microphone_status()}")))
        if backend == "local":
            stt_ready = importlib.util.find_spec("faster_whisper") is not None
            console.print(Text(f"Transcription: local faster-whisper {'installed' if stt_ready else 'not installed'}"))
        else:
            console.print(Text(f"Transcription: OpenAI Whisper key {'configured' if settings.get('openai_api_key') else 'missing'}"))
        console.print("No API calls or recordings were made. Run vocal ask or vocal voice to try it.")
        if not key_present:
            raise typer.Exit(1)
    except (ValueError, OSError) as exc:
        console.print(Text(safe_display(f"Error: {exc}"), style="red"))
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, show_version: bool = typer.Option(False, "--version", is_eager=True, help="Show the installed version.")) -> None:
    """VocalCLI: commands stay under your control."""
    if show_version:
        try:
            installed_version = version("vocalcli")
        except PackageNotFoundError:
            installed_version = "unknown (not installed)"
        console.print(Text(f"VocalCLI {installed_version}"))
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        if not sys.stdin.isatty():
            console.print("Use vocal ask 'your request' or vocal --help.")
            raise typer.Exit(1)
        try:
            while True:
                query = input("vocal> ").strip()
                if query.lower() in ("quit", "exit"):
                    break
                if query:
                    try:
                        process_query(query)
                    except (LLMError, ValueError, OSError) as exc:
                        console.print(Text(safe_display(f"Error: {exc}"), style="red"))
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")


if __name__ == "__main__":
    app()
