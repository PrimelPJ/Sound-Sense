"""Microphone capture. Keeps the last few seconds of audio in memory."""

import logging
import threading

import numpy as np

log = logging.getLogger("soundsense.audio")


class Mic:
    def __init__(self, sample_rate: int = 16000, seconds: float = 2.0, device=None) -> None:
        import sounddevice as sd  # imported here so --simulate works without audio drivers

        self.sd = sd
        self.sample_rate = sample_rate
        self.buffer = np.zeros(int(sample_rate * seconds), dtype=np.float32)
        self.lock = threading.Lock()
        self.level = 0.0
        self.stream = sd.InputStream(
            samplerate=sample_rate, channels=1, dtype="float32",
            device=device, blocksize=int(sample_rate * 0.1), callback=self._on_audio,
        )

    def _on_audio(self, indata, frames, time_info, status) -> None:
        if status:
            log.debug("audio status: %s", status)
        chunk = indata[:, 0]
        with self.lock:
            self.buffer = np.roll(self.buffer, -len(chunk))
            self.buffer[-len(chunk):] = chunk
            self.level = float(np.sqrt(np.mean(chunk ** 2)))

    def start(self) -> None:
        self.stream.start()

    def stop(self) -> None:
        self.stream.stop()
        self.stream.close()

    def last(self, seconds: float) -> np.ndarray:
        n = int(self.sample_rate * seconds)
        with self.lock:
            return self.buffer[-n:].copy()


def list_mics() -> str:
    import sounddevice as sd

    return str(sd.query_devices())
