"""Local configuration. Environment variables take precedence over the config file."""
import json
import os
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".vocal" / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or CONFIG_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Could not read configuration {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Configuration {path} must contain a JSON object")
    return data


def get_settings() -> dict[str, Any]:
    data = load_config()
    for key, env in (("gemini_api_key", "GEMINI_API_KEY"), ("openai_api_key", "OPENAI_API_KEY"),
                     ("provider", "VOCAL_PROVIDER"), ("model", "VOCAL_MODEL"),
                     ("stt_backend", "VOCAL_STT_BACKEND")):
        if os.environ.get(env):
            data[key] = os.environ[env]
    for key in ("provider", "model", "stt_backend", "whisper_model", "openai_api_key", "gemini_api_key"):
        if key in data and not isinstance(data[key], str):
            raise ValueError(f"Configuration field '{key}' must be a string")
    data.setdefault("provider", "gemini" if data.get("gemini_api_key") else "openai")
    data.setdefault("stt_backend", "openai")
    for key, valid in (("provider", {"openai", "gemini"}), ("stt_backend", {"openai", "local"})):
        data[key] = data[key].strip().lower()
        if data[key] not in valid:
            raise ValueError(f"Unsupported {key}: {data[key]}. Choose {' or '.join(sorted(valid))}.")
    return data
