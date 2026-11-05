# VocalCLI

A terminal companion that turns English or Hinglish developer requests into shell commands grounded in your current directory, OS, shell, and Git state. **Every proposed command needs your review before it can run**—including a proposed fix after a failure.

> **Early-stage software.** The safety checks catch some common dangerous patterns; they are not a sandbox and cannot detect every harmful command. Model output can be wrong. Review the whole command and use appropriate permissions or isolation.

## Quick start

Requirements: Python 3.10+, an interactive terminal, and an OpenAI or Gemini API key. Git is optional. API calls may incur provider charges. This repository is installed from source; no published PyPI release is assumed.

```sh
git clone https://github.com/abhishek-9935s/VOCAL-CLI.git
cd VOCAL-CLI
python -m venv .venv
source .venv/bin/activate
python -m pip install .
export OPENAI_API_KEY="your-key"
vocal doctor
vocal ask "show my git status"
```

On Windows PowerShell, use these commands in place of the activation and environment-variable lines:

```powershell
.\.venv\Scripts\Activate.ps1
$env:OPENAI_API_KEY = "your-key"
```

If PowerShell blocks virtual environment activation, run the interpreter directly instead: `.\.venv\Scripts\python.exe -m pip install .`, then `.\.venv\Scripts\python.exe -m vocal doctor` and `.\.venv\Scripts\python.exe -m vocal ask "show my git status"`.

To use Gemini instead, set `GEMINI_API_KEY` and `VOCAL_PROVIDER=gemini` (in PowerShell, `$env:GEMINI_API_KEY = "your-key"` and `$env:VOCAL_PROVIDER = "gemini"`). Gemini is automatically selected when its key exists and no provider was explicitly set. `vocal doctor` checks local configuration and microphone availability without sending an API request or recording audio; a configured key is not proof that the provider will accept it.

## Using VocalCLI

```sh
vocal --help
vocal --version
vocal ask "list files by size"
vocal ask "pichla commit amend kardo bina message change kiye"
vocal ask                        # prompt for text
vocal voice                      # microphone, with text fallback
vocal                            # interactive prompt; quit/exit to leave
python -m vocal ask "git status dikhao"
```

The card shows the query, environment, proposed command, explanation, risk, and warnings. Press **Enter** to run, **e** to edit, **c** to copy, or **Esc/q** to cancel. Clipboard copying requires an available system clipboard utility. The deterministic safety gate runs again after an edit. Known critical patterns and commands containing terminal-control or invisible formatting characters are blocked; other commands rated CRITICAL require typing `CONFIRM`. Edits are not re-explained by the model—review them yourself.

Interactive input **and output** terminals are required to run a command, so a redirected review card cannot accidentally lead to approval. Execution uses a child shell: `cd` or `export` cannot change your parent shell. POSIX terminal sessions use a PTY with live input/output; Windows and redirected streams use a subprocess pipe. If a command fails, you may opt in to sending its output for a suggested fix. The fix always goes through the same review and safety checks. If you decline analysis, the CLI returns the failed command's exit status.

## Configuration

Environment variables take precedence over `~/.vocal/config.json` (under the user home directory on Windows). To avoid writing secrets to disk, prefer environment variables. If using a config file, restrict its permissions. `vocal config` shows recognized settings without printing API keys.

| Environment variable | Config field | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | `openai_api_key` | OpenAI command generation and/or Whisper transcription |
| `GEMINI_API_KEY` | `gemini_api_key` | Gemini command generation |
| `VOCAL_PROVIDER` | `provider` | `openai` or `gemini` |
| `VOCAL_MODEL` | `model` | Override the provider's model |
| `VOCAL_STT_BACKEND` | `stt_backend` | `openai` or `local` |
| — | `whisper_model` | Local faster-whisper model, default `base` |

Default command models are `gpt-4o-mini` and `gemini-2.5-flash`; the chosen model must support the provider's structured JSON output. Example configuration:

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "stt_backend": "openai"
}
```

### Voice input

From the repository directory, install audio support with `python -m pip install '.[audio]'`. You may also need the operating system's PortAudio library and microphone permissions. Run `vocal voice`, press Enter to start, and speak; recording ends after silence or 30 seconds. If recording or transcription fails, you can type your request instead.

Voice uses OpenAI Whisper by default and needs `OPENAI_API_KEY`, even if Gemini generates commands. For local transcription, install `python -m pip install '.[audio,local-stt]'` and set `VOCAL_STT_BACKEND=local`. Faster-whisper may download its model on first use. Local STT does **not** make command generation offline: OpenAI or Gemini is still required.

## Privacy and safety

The request, OS/shell, working directory and Git root, up to 30 visible directory names, Git branch, up to 100 status entries (and change counts), the last three commit subjects, up to 10 stash identifiers, and detected tool names are sent to the selected LLM provider. If you opt into failure analysis, the failed command and up to the last 20 lines and 16,000 characters of **combined** output are also sent; they may contain secrets. Voice audio is sent to OpenAI when cloud STT is selected. Avoid sensitive directories or output unless you trust the provider and its data policies.

The gate is heuristic, not a shell parser or security boundary. Quoting, expansion, aliases, scripts, interpreters, shell-specific syntax and indirect operations may evade it. Risk ratings and explanations may be wrong. A missing-binary warning checks only the first token. Treat subprocess output as untrusted; commands can control the terminal. Git probes have short timeouts, but slow repositories can still increase latency. Shell detection prefers the immediate parent shell, then falls back to the login shell (or cmd on Windows); an IDE or wrapper can obscure the actual shell.

## Troubleshooting

- **Missing key:** Set the appropriate environment variable in the same terminal, then run `vocal doctor`. Selecting Gemini for commands does not supply the OpenAI key needed by cloud Whisper.
- **Provider error:** Check the key, network connection, provider quota and whether the configured model supports structured output. `vocal doctor` does not test any of these remotely.
- **No microphone / PortAudio:** Install the audio extra and system PortAudio, grant microphone permission, or use `vocal ask` instead.
- **Command not executed:** Review and execution require both stdin and stdout to be interactive terminals. Do not pipe or redirect the review card.
- **`vocal` not found:** Activate the virtual environment or use its Python executable with `-m vocal`.

## Development

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

Tests mock model calls and do not require API keys or microphone hardware. The POSIX runner also has an interactive PTY test. Provider availability, physical audio devices and host-specific terminal behavior need separate validation. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

A license has not yet been selected for this repository. Public visibility alone does not grant permission to reuse or redistribute the code; the repository owner should choose a license before inviting external reuse.
