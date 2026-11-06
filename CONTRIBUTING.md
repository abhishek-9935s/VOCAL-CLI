# Contributing

Thanks for your interest in VocalCLI. Before submitting code, check the repository's license status and discuss substantial changes with the maintainers in an issue.

## Development setup

Use Python 3.10 or newer:

```sh
git clone https://github.com/abhishek-9935s/VOCAL-CLI.git
cd VOCAL-CLI
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m pytest -q
```

For microphone work, install `.[audio]`; for local STT also install `.[local-stt]`. Hardware and provider integration require separate manual testing. The automated tests use mocks for cloud services; never commit keys, audio, personal data, or unredacted terminal output.

Please include tests for behavior changes, describe any platform-specific testing, and document changes to safety, data sent to providers, or configuration. See [SECURITY.md](SECURITY.md) for reporting security issues privately.
