import io
import sys
import types
import wave

import pytest
from typer.testing import CliRunner

from vocal.audio.capture import AudioUnavailable, record_audio
from vocal.audio.transcriber import TranscriptionError, transcribe, VOCABULARY
import vocal.cli as cli

np = pytest.importorskip("numpy")


def test_record_stops_after_speech_and_silence(monkeypatch):
    chunks = [np.full((1024, 1), 10000, dtype=np.int16)] + [np.zeros((1024, 1), dtype=np.int16) for _ in range(20)]
    class Stream:
        def __init__(self, **kwargs):
            assert kwargs["samplerate"] == 16000
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, size):
            return chunks.pop(0), False
    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(query_devices=lambda **kw: {}, InputStream=Stream))
    result = record_audio()
    assert result.dtype == np.int16
    assert result.shape == (20 * 1024,)
    assert len(chunks) == 1


def test_no_microphone(monkeypatch):
    def fail(**kwargs):
        raise OSError("no device")
    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(query_devices=fail))
    with pytest.raises(AudioUnavailable, match="no device"):
        record_audio()


def test_openai_transcription_wav(monkeypatch):
    import openai
    received = {}
    def create(**kwargs):
        received.update(kwargs)
        with wave.open(io.BytesIO(kwargs["file"].getvalue()), "rb") as wav:
            assert wav.getframerate() == 16000
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
        return types.SimpleNamespace(text="  port 3000 pe process dekho  ")
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: types.SimpleNamespace(audio=types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=create))))
    assert transcribe(np.array([0, 1, -1], dtype=np.int16), {"openai_api_key": "key"}) == "port 3000 pe process dekho"
    assert "kubernetes" in received["prompt"]


def test_local_whisper(monkeypatch):
    calls = {}
    class Model:
        def __init__(self, name, **kwargs):
            calls["name"] = name
        def transcribe(self, audio, **kwargs):
            calls["prompt"] = kwargs["initial_prompt"]
            return iter([types.SimpleNamespace(text=" git status ")]), None
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    assert transcribe(np.array([0], dtype=np.int16), {"stt_backend": "local", "whisper_model": "tiny"}) == "git status"
    assert calls == {"name": "tiny", "prompt": VOCABULARY}


def test_transcription_missing_key():
    with pytest.raises(TranscriptionError, match="OPENAI_API_KEY"):
        transcribe(np.zeros(1, dtype=np.int16), {})


def test_voice_falls_back_to_typed_query(monkeypatch):
    monkeypatch.setattr(cli, "get_settings", lambda: {})
    def fail():
        raise AudioUnavailable("no mic")
    monkeypatch.setattr(cli, "record_audio", fail)
    requests = []
    monkeypatch.setattr(cli, "_handle_query", requests.append)
    result = CliRunner().invoke(cli.app, ["voice"], input="\ntyped query\n")
    assert result.exit_code == 0
    assert requests == ["typed query"]
    assert "no mic" in result.output
