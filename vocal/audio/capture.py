"""Record mono PCM after Enter; stop after speech followed by silence."""
import time


class AudioUnavailable(Exception):
    pass


def record_audio(sample_rate: int = 16000, silence_seconds: float = 1.2,
                 threshold: float = 0.012, max_seconds: float = 30.0):
    try:
        import numpy as np
        import sounddevice as sd
    except (ImportError, OSError) as exc:
        raise AudioUnavailable(f"Audio dependencies or PortAudio unavailable: {exc}") from exc
    try:
        sd.query_devices(kind="input")
        chunks = []
        heard_voice = False
        quiet_samples = 0
        start = time.monotonic()
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", blocksize=1024) as stream:
            while time.monotonic() - start < max_seconds:
                chunk, _overflow = stream.read(1024)
                chunks.append(chunk.copy())
                rms = float(np.sqrt(np.mean((chunk.astype(np.float32) / 32768.0) ** 2)))
                if rms >= threshold:
                    heard_voice = True
                    quiet_samples = 0
                elif heard_voice:
                    quiet_samples += len(chunk)
                    if quiet_samples >= silence_seconds * sample_rate:
                        break
        if not heard_voice:
            raise AudioUnavailable("No speech detected.")
        return np.concatenate(chunks).reshape(-1)
    except AudioUnavailable:
        raise
    except Exception as exc:
        raise AudioUnavailable(f"Microphone unavailable: {exc}") from exc
