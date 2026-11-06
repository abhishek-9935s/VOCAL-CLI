import io
import wave

VOCABULARY = ("git, commit, rebase, squash, checkout, cherry-pick, branch, merge, HEAD, "
              "kubernetes, k8s, kubectl, pod, deployment, ingress, docker, container, "
              "docker-compose, prune, build, npm, pnpm, yarn, cargo, rust, python, pip, "
              "venv, poetry, lsof, chmod, chown, grep, awk, sed, systemctl, kill, SIGKILL, stdout, stderr. "
              "Preserve English and Hindi code-switching verbatim.")


class TranscriptionError(Exception):
    pass


def transcribe(audio, settings: dict, sample_rate: int = 16000) -> str:
    try:
        backend = settings.get("stt_backend", "openai")
        if backend == "local":
            import numpy as np
            from faster_whisper import WhisperModel
            model = WhisperModel(settings.get("whisper_model", "base"), device="cpu", compute_type="int8")
            segments, _ = model.transcribe(audio.astype(np.float32) / 32768.0, initial_prompt=VOCABULARY)
            text = " ".join(segment.text.strip() for segment in segments).strip()
        elif backend == "openai":
            key = settings.get("openai_api_key")
            if not key:
                raise TranscriptionError("OpenAI transcription requires OPENAI_API_KEY (or use VOCAL_STT_BACKEND=local).")
            from openai import OpenAI
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(audio.astype("<i2").tobytes())
            buffer.seek(0)
            buffer.name = "speech.wav"
            result = OpenAI(api_key=key, timeout=60).audio.transcriptions.create(model="whisper-1", file=buffer, prompt=VOCABULARY)
            text = result.text.strip()
        else:
            raise TranscriptionError(f"Unknown transcription backend: {backend}")
        if not text:
            raise TranscriptionError("Transcription was empty.")
        return text
    except TranscriptionError:
        raise
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc
