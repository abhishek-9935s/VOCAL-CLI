import pytest
import vocal.config as config


def test_config_env_precedence_and_redaction(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"provider": "openai", "openai_api_key": "secret"}')
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    assert config.get_settings()["openai_api_key"] == "environment-key"
    from typer.testing import CliRunner
    from vocal.cli import app
    result = CliRunner().invoke(app, ["config"])
    assert result.exit_code == 0
    assert "environment-key" not in result.output
    assert "secret" not in result.output


def test_bad_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[]")
    with pytest.raises(ValueError):
        config.load_config(path)


def test_invalid_setting_type_fails_cleanly(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"provider": 123}')
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    monkeypatch.delenv("VOCAL_PROVIDER", raising=False)
    with pytest.raises(ValueError, match="provider.*string"):
        config.get_settings()


def test_provider_and_transcription_case_normalized(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"provider": " OpenAI ", "stt_backend": " LOCAL "}')
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    monkeypatch.delenv("VOCAL_PROVIDER", raising=False)
    monkeypatch.delenv("VOCAL_STT_BACKEND", raising=False)
    settings = config.get_settings()
    assert settings["provider"] == "openai"
    assert settings["stt_backend"] == "local"


def test_invalid_backend_is_actionable(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"stt_backend": "nonsense"}')
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    monkeypatch.delenv("VOCAL_STT_BACKEND", raising=False)
    with pytest.raises(ValueError, match="Unsupported stt_backend"):
        config.get_settings()
